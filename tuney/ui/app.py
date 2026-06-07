import math
from collections.abc import Sequence
from queue import Queue

from customtkinter import CTk, CTkFrame
from pydantic import BaseModel

from ..keyboard.key_press import CharPress
from ..types import Callback
from . import layout

# TODO: bg_color exists but is not useful, what is?
PRESSED = {'fg_color': 'grey90', 'corner_radius': 8}
RELEASED = PRESSED | {'fg_color': 'gray60'}
HOVER = {'hover_color': '#248060'}

REPLAY = {'text': 'Replay (Ctrl+R)', 'fg_color': '#30a870', **HOVER}
STOP = {'text': 'Stop (Ctrl+R)', 'fg_color': '#b0a8b0', **HOVER}

QUEUE_POLL_IN_MS = 25
REPORT_KEYSTROKES = False


class NoteLabel(BaseModel, frozen=True):
    labels: Sequence[str]
    on: bool = False


class App(CTk):
    def __init__(self, note_labels: dict[str, NoteLabel], on_replay: Callback) -> None:
        super().__init__()
        self.note_labels = note_labels
        self._on_replay = on_replay
        self.queue = Queue[CharPress]()
        self.note_frames = dict[str, CTkFrame]()
        self.columns, self.rows = _from_length(len(note_labels))
        self.count_label, self.textbox, self.replay = layout.layout(self)
        self._is_replaying = False

        self.bind('<Control-r>', self.on_replay)
        self.bind('<Command-r>', self.on_replay)
        if REPORT_KEYSTROKES:
            self.bind('<Key>', lambda e: print(e.char, e.keysym, e.keycode))

    def start(self) -> None:
        self._handle_queue()

    def on_char(self, c: CharPress) -> None:
        if c.char:
            self.queue.put(c)

    @property
    def is_replaying(self) -> bool:
        return self._is_replaying

    @is_replaying.setter
    def is_replaying(self, is_replaying: bool) -> None:
        if self._is_replaying != is_replaying:
            self._is_replaying = is_replaying
            self.replay.configure(**(STOP if is_replaying else REPLAY))
            self._on_replay()

    def on_replay(self, *_) -> None:
        self.is_replaying = not self.is_replaying

    def get_text(self) -> str:
        return self.textbox.get('1.0', 'end-1c')

    def set_note_frame(self, key: str, frame: CTkFrame) -> None:
        self.note_frames[key] = frame

    def set_text(self, text: str) -> None:
        self.textbox.configure(state='normal')
        self.textbox.delete('1.0', 'end')
        self._append_string(text)

    def _append_string(self, s: str) -> None:
        self.textbox.configure(state='normal')
        try:
            if s == '\b':
                self.textbox.delete('end - 2c', 'end - 1c')
            else:
                self.textbox.insert('end', s)
        finally:
            self.textbox.configure(state='disabled')

    def _handle_queue(self):
        while not self.queue.empty():
            self._on_char(self.queue.get())
        self.after(QUEUE_POLL_IN_MS, self._handle_queue)

    def _on_char(self, c: CharPress) -> None:
        if frame := self.note_frames.get(c.char):
            frame.configure(**(PRESSED if c.is_press else RELEASED))

        if c.is_press:
            self._append_string(c.char)
            self.textbox.see('end')
            self.count_label.configure(text=f'Chars: {len(self.get_text())}')


def _from_length(n: int) -> tuple[int, int]:
    c = int(math.ceil(n**0.5))
    r = n // c
    return c, r + (n > (r * c))
