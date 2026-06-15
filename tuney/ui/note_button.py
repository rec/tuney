from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from customtkinter import CTkButton, CTkFrame

from ..char_press import CharPress

PAD = 16
QUARTER = PAD // 4
BIG_FONT = 'Arial', 16, 'bold'
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
        self.grid(row=row, column=column, padx=2 * QUARTER, pady=QUARTER, sticky='nsew')
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
