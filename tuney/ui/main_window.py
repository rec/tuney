from __future__ import annotations

import math
import signal
import sys
from collections.abc import Callable
from functools import cached_property
from pathlib import Path
from queue import Queue
from types import FrameType
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QFocusEvent,
    QIcon,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QMainWindow,
    QMessageBox,
)

from ..app.app import (
    clear,
    on_char,
    randomize_timing,
    save_autosave,
    window_geometry_log_data,
)
from ..app.platform_info import instrument, set_windows_app_user_model_id
from ..app.text_timing import edit_text_timing
from ..time.char_press import CharPress
from . import file_commands, key_events, startup, tuning_files
from .error_dialogs import (
    on_report_problem,
    on_show_log,
    show_audio_error,
    show_crash_report,
    show_restore_error,
)
from .file_commands import (
    on_copy_from_state,
    on_copy_text,
    on_delete_presets,
    on_load_autosave,
    on_open_config_folder,
    on_open_text_file,
    on_paste_into_state,
    on_paste_text,
    on_save,
    on_save_as_audio,
    on_save_preset,
    on_swap_with_autosave,
    on_trash_config_file,
)
from .file_dialogs import get_open_file_name, get_save_file_name
from .help import show_help
from .history import History, WindowState
from .key_events import eventFilter, keyPressEvent, keyReleaseEvent
from .main_menu import build_menu
from .replay_controls import (
    is_replaying,
    on_loop_after,
    on_loop_before,
    on_loop_replay,
    on_loop_tempo,
    on_master_gain,
    on_randomize_on_each_loop,
    on_replay,
    on_transport_state,
    set_is_replaying,
)
from .tuning_files import on_export_tuning, on_import_tuning

if TYPE_CHECKING:
    from ..app.app import App

QUEUE_POLL_IN_MS = 25
SIGNAL_POLL_IN_MS = 100
SHUTDOWN_AUDIO_WAIT_SECONDS = 2.0
ICON_PATH = Path(__file__).resolve().parents[2] / 'icon.png'
APP_NAME = 'Tuney'
MIN_PROGRAM_WIDTH = 500
MINIMUM_SIZE_ENFORCEMENT_DELAY_IN_MS = 200


class _AfterDispatcher(QObject):
    schedule = Signal(str, int, object, tuple)
    cancel = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self, app: App) -> None:
        instrument('main window init start')
        startup.set_gui(True)
        set_windows_app_user_model_id()
        if (instance := QApplication.instance()) is None:
            instrument('qapplication create')
            self.qt_app = QApplication(sys.argv[:1])
        else:
            assert isinstance(instance, QApplication)
            instrument('qapplication reuse')
            self.qt_app = instance
        self.qt_app.setApplicationName(APP_NAME)
        self.qt_app.setStyle('Fusion')
        from .layout import Layout

        super().__init__()
        instrument('main window qmainwindow ready')
        self.setWindowTitle(APP_NAME)
        if ICON_PATH.exists():
            instrument('main window icon set', path=ICON_PATH)
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.app = app
        app.__dict__['main_window'] = self
        self.queue = Queue[CharPress]()
        self.key_queue = Queue[CharPress]()
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
        self.advanced_action: QAction
        self.export_tuning_action: QAction
        self.load_autosave_action: QAction
        self.show_text_timings_action: QAction
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

    _get_open_file_name = get_open_file_name
    _get_save_file_name = get_save_file_name

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

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if (
            self.width() < MIN_PROGRAM_WIDTH
            or self.height() < self.minimum_content_height
        ):
            self.schedule_minimum_size_enforcement()

    def schedule_minimum_size_enforcement(self) -> None:
        self._minimum_size_timer.start(MINIMUM_SIZE_ENFORCEMENT_DELAY_IN_MS)

    def _enforce_minimum_size_after_resize(self) -> None:
        if QApplication.mouseButtons() != Qt.MouseButton.NoButton:
            self.schedule_minimum_size_enforcement()
        else:
            self.enforce_minimum_size()

    def enforce_minimum_size(self) -> None:
        width = max(self.width(), MIN_PROGRAM_WIDTH)
        height = max(self.height(), self.minimum_content_height)
        if width != self.width() or height != self.height():
            self.resize(width, height)

    def closeEvent(self, event: QCloseEvent) -> None:
        instrument('close event start')
        self._close_app()
        super().closeEvent(event)
        instrument('close event end')

    def _close_app(self) -> None:
        try:
            self.ui.control_panel.save_state()
            self.app._autosave.save(lambda path: save_autosave(self.app, path))
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, 'Could not save state', str(error))
        self.app.midi_listener.close()
        self.app.midi.output.close()
        self.app.player.stop_all()
        self.app.player.wait(SHUTDOWN_AUDIO_WAIT_SECONDS)
        self.app.player.close()

    def _restore_window_state(self) -> None:
        if window_state := self.app.__dict__.pop('_autosave_window_state', None):
            instrument('window restore state loaded', saved=window_state.model_dump())
            self._restored_window_state = window_state
            self._apply_restored_window_state()

    def _apply_restored_window_state(self) -> None:
        if window_state := self._restored_window_state:
            instrument(
                'window restore geometry before',
                saved=window_state.model_dump(),
                **window_geometry_log_data(self),
            )
            self.setGeometry(
                window_state.x,
                window_state.y,
                window_state.width,
                window_state.height,
            )
            instrument(
                'window restore geometry after set', **window_geometry_log_data(self)
            )
            self.enforce_minimum_size()
            instrument(
                'window restore geometry after enforce',
                **window_geometry_log_data(self),
            )

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
        clear(self.app)

    def on_advanced(self, checked: bool) -> None:
        instrument('ui advanced', checked=checked)
        self.ui.control_panel.show_mode(checked)

    def on_show_text_timings(self, checked: bool) -> None:
        instrument('ui show text timings', checked=checked)
        self.app.show_text_timings = checked
        self.update_text_display()

    def on_text_timing_changed(self, row: int, column: int, text: str) -> None:
        instrument('ui text timing changed', row=row, column=column, text=text)
        try:
            self.history.checkpoint_undo()
            edit_text_timing(self.app.char_presses, row, column, text)
        except ValueError as error:
            QMessageBox.critical(self, 'Show Text Timings', str(error))
        self.update_text_display()

    on_open_text_file = on_open_text_file
    on_save = on_save
    on_save_as_audio = on_save_as_audio
    on_save_preset = on_save_preset
    on_delete_presets = on_delete_presets

    on_import_tuning = on_import_tuning
    on_export_tuning = on_export_tuning
    _set_tuning = tuning_files.set_tuning
    _update_export_tuning_action = tuning_files.update_export_tuning_action

    on_transport_state = on_transport_state

    def on_refresh_devices(self, *_: object) -> None:
        instrument('ui refresh devices')
        self.ui.refresh_devices()

    def on_randomize_timing(self, *_: object) -> None:
        instrument('ui randomize timing')
        randomize_timing(self.app)

    def on_help(self, *_: object) -> None:
        instrument('ui help')
        show_help(self)

    on_show_log = on_show_log
    on_report_problem = on_report_problem
    show_restore_error = show_restore_error
    show_crash_report = show_crash_report
    show_audio_error = show_audio_error

    on_open_config_folder = on_open_config_folder
    on_trash_config_file = on_trash_config_file
    _config_path = file_commands.config_path
    on_copy_from_state = on_copy_from_state
    on_paste_into_state = on_paste_into_state
    on_copy_text = on_copy_text
    on_paste_text = on_paste_text
    on_load_autosave = on_load_autosave
    on_swap_with_autosave = on_swap_with_autosave

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
        widget = QApplication.focusWidget()
        while widget is not None:
            if isinstance(widget, QLineEdit | QComboBox):
                return True
            if widget is self.ui.control_panel:
                return True
            widget = widget.parentWidget()
        return False

    def changeEvent(self, event: QEvent) -> None:
        self._has_focus = self.isActiveWindow()
        super().changeEvent(event)

    def focusInEvent(self, event: QFocusEvent) -> None:
        self._has_focus = True
        super().focusInEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        self._has_focus = self.isActiveWindow()
        super().focusOutEvent(event)

    keyPressEvent = keyPressEvent
    keyReleaseEvent = keyReleaseEvent
    eventFilter = eventFilter
    _on_key_event = key_events.on_key_event

    @cached_property
    def menu(self):
        return build_menu(self)

    def sync_config_actions(self) -> None:
        if hasattr(self, 'load_autosave_action'):
            self.load_autosave_action.setChecked(self.app.load_autosave)
        if hasattr(self, 'show_text_timings_action'):
            self.show_text_timings_action.setChecked(self.app.show_text_timings)

    is_replaying = property(is_replaying, set_is_replaying)
    on_replay = on_replay
    on_loop_replay = on_loop_replay
    on_master_gain = on_master_gain
    on_loop_tempo = on_loop_tempo
    on_loop_before = on_loop_before
    on_loop_after = on_loop_after
    on_randomize_on_each_loop = on_randomize_on_each_loop

    def _handle_queue(self) -> None:
        while not self.key_queue.empty():
            on_char(self.app, self.key_queue.get())
        while not self.queue.empty():
            self._on_char(self.queue.get())
        if engine := self.app.player.__dict__.get('engine'):
            for error in engine.diagnostics.take_errors():
                self.show_audio_error(error)

    def _on_char(self, c: CharPress) -> None:
        if frame := self.ui.note_buttons.get(c.char):
            frame.is_press = c.is_press
