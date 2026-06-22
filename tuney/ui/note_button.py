from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtGui import QFont, QResizeEvent
from PySide6.QtWidgets import QGridLayout, QPushButton

from ..char_press import CharPress
from . import constants

FONT_FAMILY = 'Arial'
MAX_FONT_SIZE = 23
MIN_FONT_SIZE = 10
FONT_SCALING_THRESHOLD = 60
PRESSED_STYLE = 'background: lightgreen; color: black; border-radius: 8px;'
RELEASED_STYLE = 'background: #e5e5e5; color: black; border-radius: 8px;'


class NoteButton(QPushButton):
    def __init__(
        self,
        layout: QGridLayout,
        row: int,
        column: int,
        char: str,
        text: str,
        on_char: Callable[[CharPress], object],
    ) -> None:
        super().__init__(text)
        self.char = char
        self._on_char = on_char
        self._font_size = MAX_FONT_SIZE
        self.note_name = text
        self.setFont(QFont(FONT_FAMILY, MAX_FONT_SIZE, QFont.Weight.Bold))
        self.setMinimumSize(48, 48)
        self.clicked.connect(self.toggle)
        layout.addWidget(self, row, column)
        layout.setContentsMargins(
            constants.QUARTER,
            constants.QUARTER,
            constants.QUARTER,
            constants.QUARTER,
        )
        self.is_press = False

    @property
    def is_press(self) -> bool:
        return getattr(self, '_is_press', False)

    @is_press.setter
    def is_press(self, is_press: bool) -> None:
        self._is_press = is_press
        self.setStyleSheet(PRESSED_STYLE if is_press else RELEASED_STYLE)

    def toggle(self) -> None:
        self.is_press = not self.is_press
        self._on_char(CharPress(self.char, self.is_press, time.time()))

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        font_size = _note_font_size(self.width(), self.height())
        if font_size != self._font_size:
            self._font_size = font_size
            self.setFont(QFont(FONT_FAMILY, font_size, QFont.Weight.Bold))


def _note_font_size(width: int, height: int) -> int:
    size = min(width, height)
    if size >= FONT_SCALING_THRESHOLD:
        return MAX_FONT_SIZE
    return max(MIN_FONT_SIZE, MAX_FONT_SIZE * size // FONT_SCALING_THRESHOLD)
