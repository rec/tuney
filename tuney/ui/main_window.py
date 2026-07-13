from __future__ import annotations

import math
import signal
import sys
import time
from collections.abc import Callable
from functools import cached_property
from pathlib import Path
from queue import Queue
from types import FrameType
from typing import TYPE_CHECKING

from pydantic import ValidationError
from PySide6.QtCore import QEvent, QObject, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QFocusEvent,
    QIcon,
    QKeyEvent,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from ..app.app import (
    clear,
    dump_data,
    dump_toml,
    edit_text_timing,
    load_text_file,
    on_char,
    on_replay,
    output_comment,
    randomize_timing,
    restore_data,
    restore_text,
    save,
)
from ..app.global_config import GlobalConfig
from ..app.platform_info import error_issue_url, log_exception, log_path
from ..presets import delete_presets, read_file, user_preset_names, write_preset
from ..scale.ratios import Ratios
from ..scale.table import Table
from ..scale.tuning import Computed, Tuning, Type
from ..time.char_press import CharPress
from . import Action, StateChange, startup
from .help import show_help
from .history import History

if TYPE_CHECKING:
    from ..app.app import App

QUEUE_POLL_IN_MS = 25
SIGNAL_POLL_IN_MS = 100
ICON_PATH = Path(__file__).resolve().parents[2] / 'icon.png'
CLEAR_ACCELERATOR = 'Ctrl+B'
REFRESH_DEVICES_ACCELERATOR = 'Ctrl+D'
SAVE_ACCELERATOR = 'Ctrl+S'
UNDO_ACCELERATOR = 'Ctrl+Z'
REDO_ACCELERATOR = 'Ctrl+Y'
HELP_ACCELERATOR = QKeySequence.StandardKey.HelpContents
APP_NAME = 'Tuney'
OPEN_TEXT_FILE_COMMAND = 'Open Text File'
SAVE_COMMAND = 'Save'
IMPORT_TUNING_COMMAND = 'Import tuning...'
EXPORT_TUNING_COMMAND = 'Export tuning...'
SAVE_AUDIO_COMMAND = 'Save audio'
COMMAND_MODIFIERS = (
    Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
)
OPTION_MODIFIER = Qt.KeyboardModifier.AltModifier
KEY_TEXT = {
    Qt.Key.Key_Backspace: '\b',
    Qt.Key.Key_Enter: '\n',
    Qt.Key.Key_Return: '\n',
    Qt.Key.Key_Space: ' ',
}


class _AfterDispatcher(QObject):
    schedule = Signal(str, int, object, tuple)
    cancel = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self, app: App) -> None:
        startup.set_gui(True)
        if (instance := QApplication.instance()) is None:
            self.qt_app = QApplication(sys.argv[:1])
        else:
            assert isinstance(instance, QApplication)
            self.qt_app = instance
        self.qt_app.setApplicationName(APP_NAME)
        self.qt_app.setStyle('Fusion')
        from .layout import Layout

        super().__init__()
        self.setWindowTitle(APP_NAME)
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.app = app
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
        self._queue_timer = QTimer(self)
        self._queue_timer.timeout.connect(self._handle_queue)
        self.setMenuBar(self.menu)
        self.ui = Layout(self)
        self.setCentralWidget(self.ui)
        self.update_text_display()
        self.qt_app.installEventFilter(self)

    @cached_property
    def global_config(self) -> GlobalConfig:
        return GlobalConfig.read()

    def _get_open_file_name(
        self, command: str, title: str, filter_: str
    ) -> tuple[str, str]:
        result = QFileDialog.getOpenFileName(
            self, title, self.global_config.directory(command), filter_
        )
        self.global_config.remember_directory(command, result[0])
        return result

    def _get_save_file_name(
        self, command: str, title: str, filter_: str
    ) -> tuple[str, str]:
        result = QFileDialog.getSaveFileName(
            self, title, self.global_config.directory(command), filter_
        )
        self.global_config.remember_directory(command, result[0])
        return result

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
        self._queue_timer.start(QUEUE_POLL_IN_MS)

    def mainloop(self) -> None:
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

    def _on_sigint(self, _signum: int, _frame: FrameType | None) -> None:
        self.close()
        self.qt_app.quit()

    def activate(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self._has_focus = True

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            self.app._autosave.save(lambda path: save(self.app, path))
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, 'Could not save state', str(error))
        self.app.player.close()
        super().closeEvent(event)

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
        self.history.clear_settings()

    def on_clear_text(self, *_: object) -> None:
        clear(self.app)

    def on_advanced(self, checked: bool) -> None:
        self.ui.control_panel.show_mode(checked)

    def on_show_text_timings(self, checked: bool) -> None:
        self.app.show_text_timings = checked
        self.update_text_display()

    def on_text_timing_changed(self, row: int, column: int, text: str) -> None:
        try:
            self.history.checkpoint_undo()
            edit_text_timing(self.app, row, column, text)
        except ValueError as error:
            QMessageBox.critical(self, 'Show Text Timings', str(error))
        self.update_text_display()

    def on_open_text_file(self, *_: object) -> None:
        self._is_saving = True
        try:
            result = self._get_open_file_name(
                OPEN_TEXT_FILE_COMMAND,
                OPEN_TEXT_FILE_COMMAND,
                'Text (*.txt);;All files (*)',
            )
            if filename := result[0]:
                try:
                    load_text_file(self.app, Path(filename))
                except (OSError, ValueError) as error:
                    QMessageBox.critical(self, 'Open Text File', str(error))
        finally:
            self._is_saving = False
            self._has_focus = False

    def on_save(self, *_: object) -> None:
        self._is_saving = True
        try:
            result = self._get_save_file_name(
                SAVE_COMMAND, SAVE_COMMAND, 'TOML (*.toml);;JSON (*.json)'
            )
            if filename := result[0]:
                try:
                    save(self.app, Path(filename))
                except (OSError, ValueError) as error:
                    QMessageBox.critical(self, 'Save', str(error))
        finally:
            self._is_saving = False
            self._has_focus = False

    def on_save_preset(self, *_: object) -> None:
        if (name := _preset_name(self)) is None:
            return
        try:
            write_preset(name, dump_data(self.app))
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, 'Save preset', str(error))
            return
        self.ui.rebuild_control_panel()

    def on_delete_presets(self, *_: object) -> None:
        if not (names := _selected_preset_names(self)):
            return
        try:
            self.history.checkpoint_undo()
            delete_presets(names)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, 'Delete presets', str(error))
            return
        self.ui.rebuild_control_panel()

    def on_import_tuning(self, *_: object) -> None:
        self._is_saving = True
        try:
            result = self._get_open_file_name(
                IMPORT_TUNING_COMMAND,
                'Import tuning',
                'Scala (*.scl);;All files (*)',
            )
            if filename := result[0]:
                try:
                    self.history.checkpoint_undo()
                    self._set_tuning(Ratios.read_scala_file(Path(filename)))
                except (OSError, ValueError) as error:
                    QMessageBox.critical(self, 'Import tuning', str(error))
        finally:
            self._is_saving = False
            self._has_focus = False

    def on_export_tuning(self, *_: object) -> None:
        if (tuning := _export_tuning_source(self.app.tuning)) is None:
            return

        self._is_saving = True
        try:
            result = self._get_save_file_name(
                EXPORT_TUNING_COMMAND,
                'Export tuning',
                'Scala (*.scl);;All files (*)',
            )
            if filename := result[0]:
                try:
                    ratios = (
                        tuning if isinstance(tuning, Ratios) else tuning.as_ratios()
                    )
                    ratios.write_scala_file(Path(filename))
                except (OSError, ValueError) as error:
                    QMessageBox.critical(self, 'Export tuning', str(error))
        finally:
            self._is_saving = False
            self._has_focus = False

    def _set_tuning(self, tuning: Computed | Ratios | Table) -> None:
        data = self.app.tuning.model_dump()
        match tuning:
            case Computed():
                data |= {'type': Type.computed, 'computed': tuning}
            case Ratios():
                data |= {'type': Type.ratios, 'ratios': tuning}
            case Table():
                data |= {'type': Type.table, 'table': tuning}
        validated = type(self.app.tuning).model_validate(data)
        for field in type(self.app.tuning).model_fields:
            setattr(self.app.tuning, field, getattr(validated, field))
        self.ui.rebuild_control_panel()

    def _update_export_tuning_action(self) -> None:
        self.export_tuning_action.setEnabled(
            _export_tuning_source(self.app.tuning) is not None
        )

    def on_transport_state(self, change: StateChange) -> bool:
        filename = ''
        if change.action == Action.save:
            self._is_saving = True
            try:
                result = self._get_save_file_name(
                    SAVE_AUDIO_COMMAND,
                    SAVE_AUDIO_COMMAND,
                    'WAV (*.wav)',
                )
                filename = result[0]
            finally:
                self._is_saving = False
                self._has_focus = False
        path = Path(filename) if filename else None
        return self.app.audio_recorder.on_transport_state(
            change,
            self.app.player,
            lambda: output_comment(self.app),
            path,
        )

    def on_refresh_devices(self, *_: object) -> None:
        self.ui.refresh_devices()

    def on_randomize_timing(self, *_: object) -> None:
        randomize_timing(self.app)

    def on_help(self, *_: object) -> None:
        show_help(self)

    def on_show_log(self, *_: object) -> None:
        QMessageBox.information(
            self,
            'Tuney log',
            f'Log file:\n\n{log_path()}',
        )

    def show_restore_error(self, error: BaseException) -> None:
        path = log_exception(error)
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle('Could not restore saved state')
        dialog.setTextFormat(Qt.TextFormat.RichText)
        url = QUrl.fromLocalFile(str(path)).toString()
        dialog.setText(
            'Tuney could not fully restore its saved state and will continue with '
            'the available settings.<br><br>'
            f'<a href="{url}">Open the log file</a>'
        )
        if label := dialog.findChild(QLabel):
            label.setOpenExternalLinks(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        report = dialog.addButton('Report Issue', QMessageBox.ButtonRole.ActionRole)
        dialog.exec()
        if dialog.clickedButton() is report:
            QDesktopServices.openUrl(QUrl(error_issue_url(error, path)))

    def on_open_config_folder(self, *_: object) -> None:
        path = self.app.config_file or self.app._autosave.path
        folder = path.expanduser().parent.resolve()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            QMessageBox.critical(
                self,
                'Open enclosing folder for config file',
                f'Could not create {folder}:\n\n{error}',
            )
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
            QMessageBox.critical(
                self,
                'Open enclosing folder for config file',
                f'Could not open {folder}',
            )

    def on_copy_from_state(self, *_: object) -> None:
        self.qt_app.clipboard().setText(dump_toml(self.app))

    def on_paste_into_state(self, *_: object) -> None:
        try:
            self.history.checkpoint_undo()
            restore_text(self.app, self.qt_app.clipboard().text())
        except (ValueError, ValidationError) as error:
            QMessageBox.critical(self, 'Paste into state', str(error))
            return
        self.ui.rebuild_control_panel()
        self.ui.rebuild_note_grid()
        self.sync_config_actions()
        self.update_text_display()

    def on_load_autosave(self, checked: bool) -> None:
        if checked == self.app.load_autosave:
            return
        self.history.checkpoint_undo()
        self.app.load_autosave = checked

    def on_swap_with_autosave(self, *_: object) -> None:
        path = self.app._autosave.path
        try:
            data = read_file(path)
            type(self.app).model_validate(data)
        except (OSError, ValueError, ValidationError) as error:
            QMessageBox.critical(self, 'Swap with autosave', str(error))
            return
        try:
            self.history.checkpoint_undo()
            self.app._autosave.save(lambda path: save(self.app, path))
            restore_data(self.app, data)
        except (OSError, ValueError, ValidationError) as error:
            QMessageBox.critical(self, 'Swap with autosave', str(error))
            return
        self.sync_config_actions()
        self.ui.rebuild_control_panel()
        self.ui.rebuild_note_grid()
        self.update_text_display()

    def update_text_display(self) -> None:
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

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self._on_key_event(event, True):
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if not self._on_key_event(event, False):
            super().keyReleaseEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if isinstance(event, QKeyEvent) and not self.focus_in_control_panel:
            if event.type() == QEvent.Type.KeyPress:
                return self._on_key_event(event, True)
            if event.type() == QEvent.Type.KeyRelease:
                return self._on_key_event(event, False)
        return False

    def _on_key_event(self, event: QKeyEvent, is_press: bool) -> bool:
        if event.isAutoRepeat():
            event.ignore()
            return False
        key = event.key()
        if is_press:
            modifiers = event.modifiers()
            if modifiers & COMMAND_MODIFIERS or (
                modifiers & OPTION_MODIFIER and sys.platform != 'darwin'
            ):
                c = ''
            elif (
                not modifiers & OPTION_MODIFIER
                and (key_value := Qt.Key(key)) in KEY_TEXT
            ):
                c = KEY_TEXT[key_value]
            else:
                c = text if len(text := event.text()) == 1 else ''
            if c:
                self._key_chars[key] = c
        else:
            c = self._key_chars.pop(key, '')
        if c:
            on_char(self.app, CharPress(c, is_press, time=time.time()))
            event.accept()
            return True
        else:
            event.ignore()
            return False

    @cached_property
    def menu(self):
        menu = self.menuBar()
        file_menu = menu.addMenu('File')
        edit_menu = menu.addMenu('Edit')
        help_menu = menu.addMenu('Help')
        _add_action(edit_menu, 'Undo', UNDO_ACCELERATOR, self.history.undo)
        _add_action(edit_menu, 'Redo', REDO_ACCELERATOR, self.history.redo)
        _add_action(edit_menu, 'Randomize Timing', None, self.on_randomize_timing)
        _add_action(edit_menu, 'Clear', CLEAR_ACCELERATOR, self.on_clear)
        _add_action(edit_menu, 'Clear Text', None, self.on_clear_text)
        self.show_text_timings_action = _add_action(
            edit_menu, 'Show Text Timings', None, self.on_show_text_timings
        )
        self.show_text_timings_action.setCheckable(True)
        self.show_text_timings_action.setChecked(self.app.show_text_timings)
        self.advanced_action = _add_action(
            edit_menu, 'Advanced', None, self.on_advanced
        )
        self.advanced_action.setCheckable(True)
        self.advanced_action.setChecked(True)
        _add_action(file_menu, OPEN_TEXT_FILE_COMMAND, None, self.on_open_text_file)
        _add_action(file_menu, 'Save preset...', None, self.on_save_preset)
        _add_action(file_menu, 'Delete presets...', None, self.on_delete_presets)
        _add_action(file_menu, IMPORT_TUNING_COMMAND, None, self.on_import_tuning)
        self.export_tuning_action = _add_action(
            file_menu, EXPORT_TUNING_COMMAND, None, self.on_export_tuning
        )
        file_menu.aboutToShow.connect(self._update_export_tuning_action)
        self._update_export_tuning_action()
        _add_action(file_menu, SAVE_COMMAND, SAVE_ACCELERATOR, self.on_save)
        _add_action(
            file_menu,
            'Open enclosing folder for config file',
            None,
            self.on_open_config_folder,
        )
        _add_action(file_menu, 'Copy from state', None, self.on_copy_from_state)
        _add_action(file_menu, 'Paste into state', None, self.on_paste_into_state)
        self.load_autosave_action = _add_action(
            file_menu, 'Load autosave on start', None, self.on_load_autosave
        )
        self.load_autosave_action.setCheckable(True)
        self.load_autosave_action.setChecked(self.app.load_autosave)
        _add_action(file_menu, 'Swap with autosave', None, self.on_swap_with_autosave)
        _add_action(
            file_menu,
            'Refresh Devices',
            REFRESH_DEVICES_ACCELERATOR,
            self.on_refresh_devices,
        )
        _add_action(help_menu, 'Tuney Help', HELP_ACCELERATOR, self.on_help)
        _add_action(help_menu, 'Show Log Location', None, self.on_show_log)
        return menu

    def sync_config_actions(self) -> None:
        if hasattr(self, 'load_autosave_action'):
            self.load_autosave_action.setChecked(self.app.load_autosave)
        if hasattr(self, 'show_text_timings_action'):
            self.show_text_timings_action.setChecked(self.app.show_text_timings)

    @property
    def is_replaying(self) -> bool:
        return self._is_replaying

    @is_replaying.setter
    def is_replaying(self, is_replaying: bool) -> None:
        if self._is_replaying != is_replaying:
            self._is_replaying = is_replaying
            self.ui.set_replay_state(is_replaying)
            on_replay(self.app)

    def on_replay(self, *_: object) -> None:
        self.is_replaying = not self.is_replaying

    def on_loop_replay(self, checked: bool) -> None:
        if checked != self.history.loop_replay:
            self.history.checkpoint_undo()
            self.history.loop_replay = checked

    def on_loop_tempo(self, tempo: str) -> None:
        try:
            value = float(tempo)
        except ValueError:
            return
        if value > 0 and value != self.history.loop_tempo:
            self.history.checkpoint_undo()
            self.history.loop_tempo = value

    def on_loop_before(self, before: str) -> None:
        if (
            value := _float_or_none(before)
        ) is not None and value != self.history.loop_before:
            self.history.checkpoint_undo()
            self.history.loop_before = value

    def on_loop_after(self, after: str) -> None:
        if (
            value := _float_or_none(after)
        ) is not None and value != self.history.loop_after:
            self.history.checkpoint_undo()
            self.history.loop_after = value

    def on_randomize_on_each_loop(self, checked: bool) -> None:
        if checked != self.history.randomize_on_each_loop:
            self.history.checkpoint_undo()
            self.history.randomize_on_each_loop = checked

    def _handle_queue(self) -> None:
        while not self.key_queue.empty():
            on_char(self.app, self.key_queue.get())
        while not self.queue.empty():
            self._on_char(self.queue.get())
        if engine := self.app.player.__dict__.get('engine'):
            for error in engine.diagnostics.take_errors():
                QMessageBox.critical(self, 'Audio error', error)

    def _on_char(self, c: CharPress) -> None:
        if frame := self.ui.note_buttons.get(c.char):
            frame.is_press = c.is_press


def _add_action(
    menu: QMenu,
    text: str,
    shortcut: str | QKeySequence.StandardKey | None,
    callback: Callable[..., object],
) -> QAction:
    action = QAction(text, menu)
    if isinstance(shortcut, QKeySequence.StandardKey):
        action.setShortcuts(shortcut)
    elif shortcut:
        action.setShortcut(shortcut)
    action.triggered.connect(callback)
    menu.addAction(action)
    return action


def _preset_name(parent: QWidget) -> str | None:
    name, accepted = QInputDialog.getText(parent, 'Save preset', 'Preset name:')
    name = name.strip()
    return name if accepted and name else None


def _selected_preset_names(parent: QWidget) -> list[str]:
    names = user_preset_names()
    if not names:
        QMessageBox.information(parent, 'Delete presets', 'There are no user presets.')
        return []

    dialog = QDialog(parent)
    dialog.setWindowTitle('Delete presets')
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel('Select presets to delete:', dialog))

    presets = QListWidget(dialog)
    presets.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    presets.addItems(names)
    layout.addWidget(presets)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        dialog,
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return []
    return [i.text() for i in presets.selectedItems()]


def _export_tuning_source(tuning: Tuning) -> Computed | Ratios | None:
    match tuning.type:
        case Type.computed:
            return tuning.computed
        case Type.ratios:
            return tuning.ratios
        case Type.table | None:
            return None


def _float_or_none(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None
