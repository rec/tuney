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
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QFocusEvent,
    QIcon,
    QKeyEvent,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
)

from ..platform_info import log_path
from ..time.char_press import CharPress
from . import Action, StateChange
from .help import show_help
from .history import History

if TYPE_CHECKING:
    from ..tuney_state import TuneyState

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
COMMAND_MODIFIERS = (
    Qt.KeyboardModifier.AltModifier
    | Qt.KeyboardModifier.ControlModifier
    | Qt.KeyboardModifier.MetaModifier
)
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
    def __init__(self, state: TuneyState) -> None:
        instance = QApplication.instance()
        if instance is None:
            self.qt_app = QApplication(sys.argv[:1])
        else:
            self.qt_app = cast(QApplication, instance)
        self.qt_app.setApplicationName(APP_NAME)
        self.qt_app.setStyle('Fusion')
        from .layout import Layout

        super().__init__()
        self.setWindowTitle(APP_NAME)
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.state = state
        self.queue = Queue[CharPress]()
        self.key_queue = Queue[CharPress]()
        self._key_chars: dict[int, str] = {}
        self._after_timers: dict[str, QTimer] = {}
        self._after_count = 0
        self._after_dispatcher = _AfterDispatcher(self)
        self._after_dispatcher.schedule.connect(self._schedule_after)
        self._after_dispatcher.cancel.connect(self._cancel_after)
        n = len(state.note_labels)
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
        self.qt_app.installEventFilter(self)

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
        self.state._autosave.save(self.state.save)
        self.state.tuney.player.close()
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
        self.state.clear()

    def on_open_text_file(self, *_: object) -> None:
        self._is_saving = True
        try:
            result = QFileDialog.getOpenFileName(
                self, 'Open Text File', '', 'Text (*.txt);;All files (*)'
            )
            filename = result[0]
            if filename:
                self.state.load_text_file(Path(filename))
        finally:
            self._is_saving = False
            self._has_focus = False

    def on_clear_settings(self, *_: object) -> None:
        response = QMessageBox.question(
            self,
            'Clear settings',
            'Clear all settings and text?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response == QMessageBox.StandardButton.Yes:
            self.history.clear_settings()

    def on_save(self, *_: object) -> None:
        self._is_saving = True
        try:
            result = QFileDialog.getSaveFileName(
                self, 'Save', '', 'TOML (*.toml);;JSON (*.json)'
            )
            filename = result[0]
            if filename:
                self.state.save(Path(filename))
        finally:
            self._is_saving = False
            self._has_focus = False

    def on_transport_state(self, change: StateChange) -> bool:
        filename = ''
        if change.action == Action.save:
            self._is_saving = True
            try:
                result = QFileDialog.getSaveFileName(
                    self,
                    'Save audio',
                    '',
                    'WAV (*.wav)',
                )
                filename = result[0]
            finally:
                self._is_saving = False
                self._has_focus = False
        path = Path(filename) if filename else None
        return self.state.audio_recorder.on_transport_state(
            change,
            self.state.tuney.player,
            self.state._output_comment,
            path,
        )

    def on_refresh_devices(self, *_: object) -> None:
        self.ui.refresh_devices()

    def on_randomize_timing(self, *_: object) -> None:
        self.state.randomize_timing()

    def on_help(self, *_: object) -> None:
        show_help(self)

    def on_show_log(self, *_: object) -> None:
        QMessageBox.information(
            self,
            'Tuney log',
            f'Log file:\n\n{log_path()}',
        )

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
            if event.modifiers() & COMMAND_MODIFIERS:
                c = ''
            elif (key_value := Qt.Key(key)) in KEY_TEXT:
                c = KEY_TEXT[key_value]
            else:
                text = event.text()
                c = text if len(text) == 1 else ''
            if c:
                self._key_chars[key] = c
        else:
            c = self._key_chars.pop(key, '')
        if c:
            self.state.on_char(CharPress(c, is_press, time=time.time()))
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
        _add_action(file_menu, 'Open Text File', None, self.on_open_text_file)
        _add_action(file_menu, 'Save', SAVE_ACCELERATOR, self.on_save)
        _add_action(file_menu, 'Clear', CLEAR_ACCELERATOR, self.on_clear)
        _add_action(file_menu, 'Clear settings...', None, self.on_clear_settings)
        _add_action(
            file_menu,
            'Refresh Devices',
            REFRESH_DEVICES_ACCELERATOR,
            self.on_refresh_devices,
        )
        _add_action(help_menu, 'Tuney Help', HELP_ACCELERATOR, self.on_help)
        _add_action(help_menu, 'Show Log Location', None, self.on_show_log)
        return menu

    @property
    def is_replaying(self) -> bool:
        return self._is_replaying

    @is_replaying.setter
    def is_replaying(self, is_replaying: bool) -> None:
        if self._is_replaying != is_replaying:
            self._is_replaying = is_replaying
            self.ui.set_replay_state(is_replaying)
            self.state.on_replay()

    def on_replay(self, *_: object) -> None:
        self.is_replaying = not self.is_replaying

    def on_loop_replay(self, *_: object) -> None:
        self.history.checkpoint_undo()
        self.history.loop_replay = not self.history.loop_replay

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

    def on_randomize_on_each_loop(self, *_: object) -> None:
        self.history.checkpoint_undo()
        self.history.randomize_on_each_loop = not self.history.randomize_on_each_loop

    def _handle_queue(self) -> None:
        while not self.key_queue.empty():
            self.state.on_char(self.key_queue.get())
        while not self.queue.empty():
            self._on_char(self.queue.get())
        engine = self.state.tuney.player.__dict__.get('engine')
        if engine:
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
) -> None:
    action = QAction(text, menu)
    if isinstance(shortcut, QKeySequence.StandardKey):
        action.setShortcuts(shortcut)
    elif shortcut:
        action.setShortcut(shortcut)
    action.triggered.connect(callback)
    menu.addAction(action)


def _float_or_none(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None
