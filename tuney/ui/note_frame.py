from __future__ import annotations

from customtkinter import CTkFrame, CTkLabel

PAD = 16
QUARTER = PAD // 4
BIG_FONT = 'Arial', 16, 'bold'
PRESSED = {'fg_color': 'lightgreen', 'corner_radius': 8}
RELEASED = PRESSED | {'fg_color': 'gray90'}


class NoteFrame(CTkFrame):
    def __init__(self, parent: CTkFrame, row: int, column: int, text: str) -> None:
        super().__init__(parent)
        self.grid(row=row, column=column, padx=2 * QUARTER, pady=QUARTER, sticky='nsew')
        self.configure(**RELEASED)
        label = CTkLabel(self, text=text, font=BIG_FONT)
        label.pack(expand=True)
        self.note_name = text

    @property
    def is_press(self) -> bool:
        return getattr(self, '_is_press', False)

    @is_press.setter
    def is_press(self, is_press: bool) -> None:
        self._is_press = is_press
        self.configure(**(PRESSED if is_press else RELEASED))
