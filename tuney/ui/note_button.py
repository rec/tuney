from __future__ import annotations

import time
from collections.abc import Callable
from tkinter import Event
from typing import Any

from customtkinter import CTkButton, CTkFrame

from ..char_press import CharPress
from . import constants

FONT_FAMILY = 'Arial'
MAX_FONT_SIZE = 23
MIN_FONT_SIZE = 10
FONT_SCALING_THRESHOLD = 60
BIG_FONT = FONT_FAMILY, MAX_FONT_SIZE, 'bold'
PRESSED = {'fg_color': 'lightgreen', 'hover_color': 'lightgreen', 'corner_radius': 8}
RELEASED = {'fg_color': 'grey90', 'hover_color': 'grey90', 'corner_radius': 8}


class NoteButton(CTkButton):
    def __init__(
        self,
        parent: CTkFrame,
        row: int,
        column: int,
        char: str,
        text: str,
        on_char: Callable[[CharPress], Any],
    ) -> None:
        super().__init__(
            parent,
            text=text,
            command=self.toggle,
            font=BIG_FONT,
            text_color='black',
        )
        self.char = char
        self._on_char = on_char
        self._font_size = MAX_FONT_SIZE
        self._resize_after_id: str | None = None
        self.bind('<Configure>', self._queue_font_resize)
        self.grid(
            row=row,
            column=column,
            padx=2 * constants.QUARTER,
            pady=constants.QUARTER,
            sticky='nsew',
        )
        self.configure(**RELEASED)
        self.note_name = text

    @property
    def is_press(self) -> bool:
        return getattr(self, '_is_press', False)

    @is_press.setter
    def is_press(self, is_press: bool) -> None:
        self._is_press = is_press
        self.configure(**(PRESSED if is_press else RELEASED))

    def toggle(self) -> None:
        self.is_press = not self.is_press
        self._on_char(CharPress(self.char, self.is_press, time.time()))

    def _queue_font_resize(self, _: Event) -> None:
        if self._resize_after_id is not None:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after_idle(self._resize_font)

    def _resize_font(self) -> None:
        self._resize_after_id = None
        font_size = _note_font_size(self.winfo_width(), self.winfo_height())
        if font_size != self._font_size:
            self._font_size = font_size
            self.configure(font=(FONT_FAMILY, font_size, 'bold'))


def _note_font_size(width: int, height: int) -> int:
    size = min(width, height)
    if size >= FONT_SCALING_THRESHOLD:
        return MAX_FONT_SIZE
    return max(MIN_FONT_SIZE, MAX_FONT_SIZE * size // FONT_SCALING_THRESHOLD)
