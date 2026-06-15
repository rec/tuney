import math
from collections.abc import Callable, Sequence
from functools import cached_property
from queue import Queue
from typing import Any

from customtkinter import CTk
from pydantic import BaseModel

from ..keyboard.key_press import CharPress

# TODO: bg_color exists but is not useful, what is?
HOVER = {'hover_color': '#248060'}

REPLAY = {'text': 'Replay (Ctrl+R)', 'fg_color': '#30a870', **HOVER}
STOP = {'text': 'Stop (Ctrl+R)', 'fg_color': '#b0a8b0', **HOVER}

QUEUE_POLL_IN_MS = 25


class NoteLabel(BaseModel, frozen=True):
    labels: Sequence[str]
    on: bool = False

    @cached_property
    def text(self) -> str:
        return '\n'.join(self.labels)


class App(CTk):
    def __init__(
        self, note_labels: dict[str, NoteLabel], on_replay: Callable[[], Any], text: str
    ) -> None:
        from .layout import Layout

        super().__init__()
        self.note_labels = note_labels
        self._on_replay = on_replay
        self.queue = Queue[CharPress]()
        n = len(note_labels)
        c = int(math.ceil(n**0.5))
        r = n // c
        r += n > (r * c)
        self.rows, self.columns = r, c
        self._is_replaying = False

        self.bind('<Control-r>', self.on_replay)
        self.bind('<Command-r>', self.on_replay)
        self.layout = Layout(self, text)

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
            self.layout.replay.configure(**(STOP if is_replaying else REPLAY))
            self._on_replay()

    def on_replay(self, *_) -> None:
        self.is_replaying = not self.is_replaying

    def _handle_queue(self):
        while not self.queue.empty():
            self._on_char(self.queue.get())
        self.after(QUEUE_POLL_IN_MS, self._handle_queue)

    def _on_char(self, c: CharPress) -> None:
        if frame := self.layout.note_buttons.get(c.char):
            frame.is_press = c.is_press
