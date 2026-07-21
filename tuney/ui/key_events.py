from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QMainWindow

from ..app.app import on_char
from ..time.char_press import CharPress

if TYPE_CHECKING:
    from .main_window import MainWindow

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


def keyPressEvent(main_window: MainWindow, event: QKeyEvent) -> None:
    if not main_window._on_key_event(event, True):
        QMainWindow.keyPressEvent(main_window, event)


def keyReleaseEvent(main_window: MainWindow, event: QKeyEvent) -> None:
    if not main_window._on_key_event(event, False):
        QMainWindow.keyReleaseEvent(main_window, event)


def eventFilter(main_window: MainWindow, watched: QObject, event: QEvent) -> bool:
    if isinstance(event, QKeyEvent) and not main_window.focus_in_control_panel:
        if event.type() == QEvent.Type.KeyPress:
            return main_window._on_key_event(event, True)
        if event.type() == QEvent.Type.KeyRelease:
            return main_window._on_key_event(event, False)
    return False


def on_key_event(main_window: MainWindow, event: QKeyEvent, is_press: bool) -> bool:
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
        elif not modifiers & OPTION_MODIFIER and (key_value := Qt.Key(key)) in KEY_TEXT:
            c = KEY_TEXT[key_value]
        else:
            c = text if len(text := event.text()) == 1 else ''
        if c:
            main_window._key_chars[key] = c
    else:
        c = main_window._key_chars.pop(key, '')
    if c:
        on_char(main_window.app, CharPress(c, is_press, time=time.time()))
        event.accept()
        return True
    event.ignore()
    return False
