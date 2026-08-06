from __future__ import annotations

import math
import signal
import sys
from collections.abc import Callable
from functools import cached_property
from pathlib import Path
from queue import Queue
from threading import Event, Thread
from types import FrameType
from typing import TYPE_CHECKING, Protocol

from PySide6 import QtGui, QtWidgets
from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer, Signal, Slot

from ..app.platform_info import instrument, report_error, set_windows_app_user_model_id
from ..app.runnable import start_thread
from ..app.text_timing import edit_text_timing
from ..midi.ports import direct_midi_names, midi_names
from ..time.char_press import CharPress
from . import error_dialogs
from . import file_commands
from . import key_events
from . import replay_controls
from . import startup
from . import tuning_files
from .file_dialogs import get_open_file_name, get_save_file_name
from .help import show_help
from .history import History, WindowState
from .main_menu import build_menu
from .theme import Theme, ThemeName, set_app_theme, theme_for_name

if TYPE_CHECKING:
    from ..app.app import App
    from ..scale.ratios import Ratios
    from ..scale.table import Table
    from ..scale.tuning import Computed
    from .state import StateChange

QUEUE_POLL_IN_MS = 25
SIGNAL_POLL_IN_MS = 100
MIDI_DEVICE_POLL_IN_SECONDS = 2
SHUTDOWN_AUDIO_WAIT_SECONDS = 2.0
ICON_PATH = Path(__file__).resolve().parents[2] / 'icon.png'
APP_NAME = 'Tuney'
MIN_PROGRAM_WIDTH = 500
MINIMUM_SIZE_ENFORCEMENT_DELAY_IN_MS = 200


class _AfterDispatcher(QObject):
    schedule = Signal(str, int, object, tuple)
    cancel = Signal(str)


class _WindowRect(Protocol):
    def x(self) -> int: ...

    def y(self) -> int: ...

    def width(self) -> int: ...

    def height(self) -> int: ...


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, app: App) -> None:
        instrument('main window init start')
        startup.set_gui(True)
        set_windows_app_user_model_id()
        if (instance := QtWidgets.QApplication.instance()) is None:
            instrument('qapplication create')
            self.qt_app = QtWidgets.QApplication(sys.argv[:1])
        else:
            assert isinstance(instance, QtWidgets.QApplication)
            instrument('qapplication reuse')
            self.qt_app = instance
        self.qt_app.setApplicationName(APP_NAME)
        self.qt_app.setStyle('Fusion')
        set_app_theme(self.qt_app, theme_for_name(app.global_config.theme))
        from .layout import Layout

        super().__init__()
        instrument('main window qmainwindow ready')
        self.setWindowTitle(APP_NAME)
        if ICON_PATH.exists():
            instrument('main window icon set', path=ICON_PATH)
            self.setWindowIcon(QtGui.QIcon(str(ICON_PATH)))
        self.app = app
        app.__dict__['main_window'] = self
        self.queue = Queue[CharPress]()
        self.key_queue = Queue[CharPress]()
        self.midi_device_queue = Queue[list[list[str]]]()
        self._midi_device_stop = Event()
        self._midi_device_thread: Thread | None = None
        self._key_chars: dict[int, str] = {}
        self._after_timers: dict[str, QTimer] = {}
        self._after_count = 0
        self._after_dispatcher = _AfterDispatcher(self)
        self._after_dispatcher.schedule.connect(self._schedule_after)
        self._after_dispatcher.cancel.connect(self._cancel_after)
        n = len(app.note_labels)
        c = int(math.ceil(n**0.5))
        r = n // c
        r += n > (r * c)
        self.rows, self.columns = r, c
        self._is_replaying = False
        self.history = History(self)
        self._is_saving = False
        self._has_focus = True
        self.minimum_content_height = 0
        self._minimum_size_timer = QTimer(self)
        self._minimum_size_timer.setSingleShot(True)
        self._minimum_size_timer.timeout.connect(
            self._enforce_minimum_size_after_resize
        )
        self._restored_window_state: WindowState | None = None
        self._queue_timer = QTimer(self)
        self._queue_timer.timeout.connect(self._handle_queue)
        self.advanced_action: QtGui.QAction
        self.dark_mode_action: QtGui.QAction
        self.export_tuning_action: QtGui.QAction
        self.load_autosave_action: QtGui.QAction
        self.show_text_timings_action: QtGui.QAction
        self.setMenuBar(self.menu)
        instrument('layout construct start')
        self.ui = Layout(self)
        instrument('layout construct end')
        self.setCentralWidget(self.ui)
        self.enforce_minimum_size()
        self._restore_window_state()
        self.update_text_display()
        self.qt_app.installEventFilter(self)
        instrument('main window init end')

    def _get_open_file_name(
        self,
        caption: str,
        dialog_key: str,
        filter_: str,
    ) -> tuple[str, str]:
        return get_open_file_name(self, caption, dialog_key, filter_)

    def _get_save_file_name(
        self,
        caption: str,
        dialog_key: str,
        filter_: str,
    ) -> tuple[str, str]:
        return get_save_file_name(self, caption, dialog_key, filter_)

    def after(self, delay: int, callback: Callable[..., object], *args: object) -> str:
        after_id = f'after-{self._after_count}'
        self._after_count += 1
        self._after_dispatcher.schedule.emit(after_id, delay, callback, args)
        return after_id

    @Slot(str, int, object, tuple)
    def _schedule_after(
        self,
        after_id: str,
        delay: int,
        callback: Callable[..., object],
        args: tuple[object, ...],
    ) -> None:
        timer = QTimer(self)
        timer.setSingleShot(True)

        def fire() -> None:
            self._after_timers.pop(after_id, None)
            callback(*args)

        timer.timeout.connect(fire)
        self._after_timers[after_id] = timer
        timer.start(delay)

    def after_cancel(self, after_id: str) -> None:
        self._after_dispatcher.cancel.emit(after_id)

    @Slot(str)
    def _cancel_after(self, after_id: str) -> None:
        if timer := self._after_timers.pop(after_id, None):
            timer.stop()
            timer.deleteLater()

    def start(self) -> None:
        instrument('main window start')
        self._queue_timer.start(QUEUE_POLL_IN_MS)

    def start_midi_device_monitor(self) -> None:
        if self._midi_device_thread is not None:
            return
        self._midi_device_stop.clear()
        self._midi_device_thread = start_thread(self._watch_midi_devices)

    def sync_midi_device_monitor(self) -> None:
        if self.app.midi.input.enable or self.app.midi.output.enable:
            self.start_midi_device_monitor()
        else:
            self._stop_midi_device_monitor()

    def _watch_midi_devices(self) -> None:
        names = direct_midi_names()
        midi_names.replace(names)
        while not self._midi_device_stop.wait(MIDI_DEVICE_POLL_IN_SECONDS):
            updated = direct_midi_names()
            if updated != names:
                names = updated
                midi_names.replace(updated)
                self.midi_device_queue.put(updated)

    def mainloop(self) -> None:
        instrument('qt exec enter')
        old_handler = signal.getsignal(signal.SIGINT)
        signal_timer = QTimer(self)
        signal_timer.timeout.connect(lambda: None)
        signal_timer.start(SIGNAL_POLL_IN_MS)
        signal.signal(signal.SIGINT, self._on_sigint)
        try:
            self.activate()
            self.qt_app.exec()
        finally:
            signal_timer.stop()
            signal_timer.deleteLater()
            signal.signal(signal.SIGINT, old_handler)
            instrument('qt exec leave')

    def _on_sigint(self, _signum: int, _frame: FrameType | None) -> None:
        self.close()
        self.qt_app.quit()

    def activate(self) -> None:
        instrument('main window activate')
        self.show()
        self._apply_restored_window_state()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self._has_focus = True
        QTimer.singleShot(0, self._finish_activate)

    def _finish_activate(self) -> None:
        self._apply_restored_window_state()
        self.enforce_minimum_size()
        self.ui.refresh_note_button_fonts()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if (
            self.width() < MIN_PROGRAM_WIDTH
            or self.height() < self.minimum_content_height
        ):
            self.schedule_minimum_size_enforcement()

    def schedule_minimum_size_enforcement(self) -> None:
        self._minimum_size_timer.start(MINIMUM_SIZE_ENFORCEMENT_DELAY_IN_MS)

    def _enforce_minimum_size_after_resize(self) -> None:
        if QtWidgets.QApplication.mouseButtons() != Qt.MouseButton.NoButton:
            self.schedule_minimum_size_enforcement()
        else:
            self.enforce_minimum_size()

    def enforce_minimum_size(self) -> None:
        width = max(self.width(), MIN_PROGRAM_WIDTH)
        height = max(self.height(), self.minimum_content_height)
        if width != self.width() or height != self.height():
            self.resize(width, height)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        instrument('close event start')
        self._close_app()
        super().closeEvent(event)
        instrument('close event end')

    def _close_app(self) -> None:
        try:
            self.ui.control_panel.save_state()
            self.app._autosave.save(self.app.save_autosave)
        except (OSError, ValueError) as error:
            QtWidgets.QMessageBox.critical(self, 'Could not save state', str(error))
        self.app.midi_listener.close()
        if hasattr(self, '_stop_midi_device_monitor'):
            self._stop_midi_device_monitor()
        self.app.midi.output.close()
        self.app.player.stop_all()
        self.app.player.wait(SHUTDOWN_AUDIO_WAIT_SECONDS)
        self.app.player.close()

    def _stop_midi_device_monitor(self) -> None:
        self._midi_device_stop.set()
        if self._midi_device_thread is not None:
            self._midi_device_thread.join(timeout=1)
            self._midi_device_thread = None

    def _restore_window_state(self) -> None:
        if window_state := self.app.__dict__.pop('_autosave_window_state', None):
            instrument('window restore state loaded', saved=window_state.model_dump())
            self._restored_window_state = window_state
            self._apply_restored_window_state()

    def _apply_restored_window_state(self) -> None:
        if window_state := self._restored_window_state:
            restored_window_state = visible_restored_window_state(self, window_state)
            instrument(
                'window restore geometry before',
                saved=window_state.model_dump(),
                applied=restored_window_state.model_dump(),
                **self.geometry_log_data(),
            )
            self.setGeometry(
                restored_window_state.x,
                restored_window_state.y,
                restored_window_state.width,
                restored_window_state.height,
            )
            instrument('window restore geometry after set', **self.geometry_log_data())
            self.enforce_minimum_size()
            instrument(
                'window restore geometry after enforce',
                **self.geometry_log_data(),
            )

    def geometry_log_data(self) -> dict[str, object]:
        return {
            'direct': {
                'x': self.x(),
                'y': self.y(),
                'width': self.width(),
                'height': self.height(),
            },
            'geometry': _window_rect_value(self.geometry()),
            'frame_geometry': _window_rect_value(self.frameGeometry()),
            'normal_geometry': _window_rect_value(self.normalGeometry()),
            'window_state': self.windowState(),
            'is_maximized': self.isMaximized(),
            'is_minimized': self.isMinimized(),
            'is_full_screen': self.isFullScreen(),
        }

    def destroy(
        self, destroyWindow: bool = True, destroySubWindows: bool = True
    ) -> None:
        self.close()

    def on_char(self, c: CharPress) -> None:
        if c.char:
            self.queue.put(c)

    def on_key(self, c: CharPress) -> None:
        if c.char:
            self.key_queue.put(c)

    def on_clear(self, *_: object) -> None:
        instrument('ui clear')
        self.history.clear_settings()

    def on_clear_text(self, *_: object) -> None:
        instrument('ui clear text')
        self.app.clear()

    def on_advanced(self, checked: bool) -> None:
        instrument('ui advanced', checked=checked)
        self.ui.control_panel.show_mode(checked)

    def on_show_text_timings(self, checked: bool) -> None:
        instrument('ui show text timings', checked=checked)
        self.app.show_text_timings = checked
        self.update_text_display()

    def on_dark_mode(self, checked: bool) -> None:
        instrument('ui dark mode', checked=checked)
        self.app.global_config.theme = ThemeName.dark if checked else ThemeName.light
        try:
            self.app.global_config.save()
        except OSError as error:
            report_error(
                f'Could not save global config {self.app.global_config.path}: {error}'
            )
        set_app_theme(self.qt_app, self.current_theme)
        self.ui.refresh_theme()
        self.sync_config_actions()

    def on_midi_output_failed(self, error: str) -> None:
        QtWidgets.QMessageBox.warning(
            self,
            'MIDI output failed',
            f'MIDI output failed: error {error}',
        )
        self.ui.rebuild_control_panel()
        try:
            self.app._autosave.save(self.app.save_autosave)
        except (OSError, ValueError) as save_error:
            report_error(
                f'Could not save autosave after MIDI output failure: {save_error}'
            )

    def on_text_timing_changed(self, row: int, column: int, text: str) -> None:
        instrument('ui text timing changed', row=row, column=column, text=text)
        try:
            self.history.checkpoint_undo()
            edit_text_timing(self.app.char_presses, row, column, text)
        except ValueError as error:
            QtWidgets.QMessageBox.critical(self, 'Show Text Timings', str(error))
        self.update_text_display()

    def on_open_text_file(self, *_: object) -> None:
        file_commands.on_open_text_file(self, *_)

    def on_save(self, *_: object) -> None:
        file_commands.on_save(self, *_)

    def on_save_as_audio(self, *_: object) -> None:
        file_commands.on_save_as_audio(self, *_)

    def on_save_preset(self, *_: object) -> None:
        file_commands.on_save_preset(self, *_)

    def on_save_test_sheet(self, *_: object) -> None:
        file_commands.on_save_test_sheet(self, *_)

    def on_delete_presets(self, *_: object) -> None:
        file_commands.on_delete_presets(self, *_)

    def on_import_tuning(self, *_: object) -> None:
        tuning_files.on_import_tuning(self, *_)

    def on_export_tuning(self, *_: object) -> None:
        tuning_files.on_export_tuning(self, *_)

    def _set_tuning(self, tuning: Computed | Ratios | Table) -> None:
        tuning_files.set_tuning(self, tuning)

    def _update_export_tuning_action(self) -> None:
        tuning_files.update_export_tuning_action(self)

    def on_transport_state(self, change: StateChange) -> bool:
        return replay_controls.on_transport_state(self, change)

    def on_refresh_devices(self, *_: object) -> None:
        instrument('ui refresh devices')
        self.ui.refresh_devices()

    def on_randomize_timing(self, *_: object) -> None:
        instrument('ui randomize timing')
        self.app.randomize_timing()

    def on_help(self, *_: object) -> None:
        instrument('ui help')
        show_help(self)

    def on_show_log(self, *_: object) -> None:
        error_dialogs.on_show_log(self, *_)

    def on_report_problem(self, *_: object) -> None:
        error_dialogs.on_report_problem(self, *_)

    def show_restore_error(self, error: BaseException) -> None:
        error_dialogs.show_restore_error(self, error)

    def show_crash_report(self) -> None:
        error_dialogs.show_crash_report(self)

    def show_audio_error(self, error: str) -> None:
        error_dialogs.show_audio_error(self, error)

    def on_open_config_folder(self, *_: object) -> None:
        file_commands.on_open_config_folder(self, *_)

    def on_trash_config_file(self, *_: object) -> None:
        file_commands.on_trash_config_file(self, *_)

    def _config_path(self) -> Path:
        return file_commands.config_path(self)

    def on_copy_from_state(self, *_: object) -> None:
        file_commands.on_copy_from_state(self, *_)

    def on_paste_into_state(self, *_: object) -> None:
        file_commands.on_paste_into_state(self, *_)

    def on_copy_text(self, *_: object) -> None:
        file_commands.on_copy_text(self, *_)

    def on_paste_text(self, *_: object) -> None:
        file_commands.on_paste_text(self, *_)

    def on_load_autosave(self, checked: bool) -> None:
        file_commands.on_load_autosave(self, checked)

    def on_swap_with_autosave(self, *_: object) -> None:
        file_commands.on_swap_with_autosave(self, *_)

    def update_text_display(self) -> None:
        instrument('ui update text display', timings=self.app.show_text_timings)
        if self.app.show_text_timings:
            self.ui.set_text_timings(self.app.display_text_timings)
        else:
            self.ui.set_text(self.app.display_text)

    @property
    def is_saving(self) -> bool:
        return self._is_saving

    @property
    def has_focus(self) -> bool:
        return self._has_focus or self.isActiveWindow()

    @property
    def focus_in_control_panel(self) -> bool:
        widget = QtWidgets.QApplication.focusWidget()
        while widget is not None:
            if isinstance(widget, QtWidgets.QLineEdit | QtWidgets.QComboBox):
                return True
            if widget is self.ui.control_panel:
                return True
            widget = widget.parentWidget()
        return False

    def changeEvent(self, event: QEvent) -> None:
        self._has_focus = self.isActiveWindow()
        super().changeEvent(event)

    def focusInEvent(self, event: QtGui.QFocusEvent) -> None:
        self._has_focus = True
        super().focusInEvent(event)

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        self._has_focus = self.isActiveWindow()
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        key_events.keyPressEvent(self, event)

    def keyReleaseEvent(self, event: QtGui.QKeyEvent) -> None:
        key_events.keyReleaseEvent(self, event)

    def eventFilter(self, source: QObject, event: QEvent) -> bool:
        return key_events.eventFilter(self, source, event)

    def _on_key_event(self, event: QtGui.QKeyEvent, is_press: bool) -> bool:
        return key_events.on_key_event(self, event, is_press)

    @cached_property
    def menu(self):
        return build_menu(self)

    @property
    def current_theme(self) -> Theme:
        return theme_for_name(self.app.global_config.theme)

    def sync_config_actions(self) -> None:
        if hasattr(self, 'load_autosave_action'):
            self.load_autosave_action.setChecked(self.app.load_autosave)
        if hasattr(self, 'show_text_timings_action'):
            self.show_text_timings_action.setChecked(self.app.show_text_timings)
        if hasattr(self, 'dark_mode_action'):
            self.dark_mode_action.setChecked(self.current_theme.name == ThemeName.dark)

    @property
    def is_replaying(self) -> bool:
        return replay_controls.is_replaying(self)

    @is_replaying.setter
    def is_replaying(self, value: bool) -> None:
        replay_controls.set_is_replaying(self, value)

    def on_replay(self, *_: object) -> None:
        replay_controls.on_replay(self, *_)

    def on_loop_replay(self, checked: bool) -> None:
        replay_controls.on_loop_replay(self, checked)

    def on_master_gain(self, master_gain: float) -> None:
        replay_controls.on_master_gain(self, master_gain)

    def on_loop_tempo(self, tempo: float | str) -> None:
        replay_controls.on_loop_tempo(self, tempo)

    def on_loop_before(self, before: str) -> None:
        replay_controls.on_loop_before(self, before)

    def on_loop_after(self, after: str) -> None:
        replay_controls.on_loop_after(self, after)

    def on_randomize_on_each_loop(self, checked: bool) -> None:
        replay_controls.on_randomize_on_each_loop(self, checked)

    def _handle_queue(self) -> None:
        while not self.key_queue.empty():
            self.app.on_char(self.key_queue.get())
        while not self.queue.empty():
            self._on_char(self.queue.get())
        if midi_device_queue := getattr(self, 'midi_device_queue', None):
            while not midi_device_queue.empty():
                self._on_midi_devices_changed(midi_device_queue.get())
        if engine := self.app.player.__dict__.get('engine'):
            for error in engine.diagnostics.take_errors():
                self.show_audio_error(error)

    def _on_midi_devices_changed(self, names: list[list[str]]) -> None:
        output_name = self.app.midi.output.name
        self.ui.refresh_midi_devices()
        if output_name and output_name not in names[1]:
            self.app.midi.output.close()
            self.app.midi.output.name = None
            self.ui.refresh_midi_devices()
            QtWidgets.QMessageBox.information(
                self,
                'MIDI output device missing',
                f'Output device {output_name} no longer exists',
            )
            try:
                self.app._autosave.save(self.app.save_autosave)
            except (OSError, ValueError) as error:
                report_error(
                    f'Could not save autosave after MIDI output disappeared: {error}'
                )

    def _on_char(self, c: CharPress) -> None:
        if frame := self.ui.note_buttons.get(c.char):
            frame.is_press = c.is_press


def visible_restored_window_state(
    window: MainWindow, window_state: WindowState
) -> WindowState:
    screen = None
    if QtWidgets.QApplication.instance() is not None:
        screen = QtWidgets.QApplication.screenAt(QPoint(window_state.x, window_state.y))
    if screen is None:
        screen_method = getattr(window, 'screen', None)
        if callable(screen_method):
            screen = screen_method()
    if screen is None and QtWidgets.QApplication.instance() is not None:
        screen = QtWidgets.QApplication.primaryScreen()
    if screen is None:
        return window_state
    available = screen.availableGeometry()
    y = max(window_state.y, available.y())
    if y == window_state.y:
        return window_state
    return WindowState(
        x=window_state.x,
        y=y,
        width=window_state.width,
        height=window_state.height,
    )


def _window_rect_value(rect: _WindowRect) -> dict[str, int]:
    return {
        'x': rect.x(),
        'y': rect.y(),
        'width': rect.width(),
        'height': rect.height(),
    }
