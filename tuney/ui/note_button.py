from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QGridLayout, QPushButton, QSizePolicy

from ..time.char_press import CharPress
from . import constants
from .theme import note_button_style, widget_theme
from .tooltip import Tooltip

FONT_FAMILY = 'Arial'
MIN_BUTTON_WIDTH = 8
MIN_BUTTON_HEIGHT = 30
MAX_FONT_SIZE = 23
MIN_FONT_SIZE = 4
TEXT_PADDING = 4


class NoteButton(QPushButton):
    def __init__(
        self,
        layout: QGridLayout,
        row: int,
        column: int,
        char: str,
        text: str,
        tooltip_text: str,
        hover_time: Callable[[], float],
        on_char: Callable[[CharPress], object],
    ) -> None:
        super().__init__(text)
        self.char = char
        self._on_char = on_char
        self._font_size = MAX_FONT_SIZE
        self.note_name = text
        self.tooltip = Tooltip(self, tooltip_text, hover_time)
        self.setFont(QFont(FONT_FAMILY, MAX_FONT_SIZE, QFont.Weight.Bold))
        self.setMinimumSize(MIN_BUTTON_WIDTH, MIN_BUTTON_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.clicked.connect(self.toggle)
        layout.addWidget(self, row, column)
        layout.setContentsMargins(
            constants.QUARTER,
            constants.QUARTER,
            constants.QUARTER,
            constants.QUARTER,
        )
        self.is_press = False

    def set_note(self, text: str) -> None:
        if text != self.note_name:
            self.note_name = text
            self.setText(text)

    def set_tooltip_text(self, text: str) -> None:
        self.tooltip.text = text

    @property
    def is_press(self) -> bool:
        return getattr(self, '_is_press', False)

    @is_press.setter
    def is_press(self, is_press: bool) -> None:
        self._is_press = is_press
        self.refresh_theme()

    def refresh_theme(self) -> None:
        self.setStyleSheet(note_button_style(widget_theme(self), self.is_press))

    def toggle(self) -> None:
        self.is_press = not self.is_press
        self._on_char(CharPress(self.char, self.is_press, time.time()))

    def set_note_font_size(self, font_size: int) -> None:
        if font_size != self._font_size:
            self._font_size = font_size
            self.setFont(QFont(FONT_FAMILY, font_size, QFont.Weight.Bold))


def _note_font_size(width: int, height: int, text: str) -> int:
    for size in range(MAX_FONT_SIZE, MIN_FONT_SIZE, -1):
        if _font_fits(width, height, text, size):
            return size
    return MIN_FONT_SIZE


def _font_fits(width: int, height: int, text: str, size: int) -> bool:
    font = QFont(FONT_FAMILY, size, QFont.Weight.Bold)
    metrics = QFontMetrics(font)
    lines = text.splitlines() or ['']
    return max(metrics.horizontalAdvance(i) for i in lines) <= max(
        1, width - TEXT_PADDING
    ) and metrics.lineSpacing() * len(lines) <= max(1, height - TEXT_PADDING)
