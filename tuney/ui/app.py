import dataclasses as dc
import math
from collections.abc import Sequence
from queue import Queue

from customtkinter import CTk
from pynput.keyboard import Key

from ..keyboard.modifiers import KeyPress
from ..types import Callback
from . import grid_ui

# TODO: bg_color is not useful, what is?
PRESSED = {'fg_color': 'grey90', 'corner_radius': 8}
RELEASED = PRESSED | {'fg_color': 'gray60'}

QUEUE_POLL_IN_MS = 25
KEYS = {Key.space: ' ', Key.enter: '\n', Key.backspace: '\b'}


@dc.dataclass
class NoteLabel:
    labels: Sequence[str]
    on: bool = False


def from_length(n: int) -> tuple[int, int]:
    c = int(math.ceil(n**0.5))
    r = n // c
    return c, r + (n > (r * c))


class App(CTk):
    def __init__(
        self,
        note_labels: dict[str, NoteLabel],
        starting_text: str,
        on_replay: Callback,
    ) -> None:
        super().__init__()
        self.note_labels = note_labels
        self.on_replay = on_replay
        self.char_count = 0
        self.queue = Queue[tuple[str, bool]]()
        self.notes = {}
        self.columns, self.rows = from_length(len(note_labels))
        self.count_label, self.textbox = grid_ui.setup(self)
        self._append_string(starting_text)

        self.bind('<Control-r>', lambda _: on_replay)
        self.bind('<Command-r>', lambda _: on_replay)

    def start(self) -> None:
        self._handle_queue()

    def on_char(self, char: str, is_press: bool) -> None:
        self.queue.put((char, is_press))

    def on_key(self, k: KeyPress) -> None:
        if char := KEYS.get(k.key) or getattr(k.key, 'char', ''):
            self.on_char(char, k.is_press)

    @property
    def text(self) -> str:
        return self.textbox.get('1.0', 'end-1c')

    def _handle_queue(self):
        while not self.queue.empty():
            char, is_press = self.queue.get()
            self._on_char(char, is_press)
        self.after(QUEUE_POLL_IN_MS, self._handle_queue)

    def _append_string(self, s: str) -> None:
        self.textbox.configure(state='normal')
        try:
            if s == '\b':
                self.char_count -= 1
                self.textbox.delete('end - 2c', 'end - 1c')
            else:
                self.char_count += len(s)
                self.textbox.insert('end', s)
        finally:
            self.textbox.configure(state='disabled')

    def _on_char(self, char: str, is_press: bool) -> None:
        if char in self.notes:
            self.notes[char].configure(**(PRESSED if is_press else RELEASED))
        if is_press:
            self._append_string(char)
            self.textbox.see('end')
            self.count_label.configure(text=f'Chars: {self.char_count}')
