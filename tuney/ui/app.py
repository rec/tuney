from __future__ import annotations

import math
import sys
from collections.abc import Sequence
from copy import deepcopy
from functools import cached_property
from pathlib import Path
from queue import Queue
from tkinter import Menu, Misc, PhotoImage, filedialog, messagebox
from typing import TYPE_CHECKING

from customtkinter import CTk, CTkEntry
from pydantic import BaseModel

from ..char_press import CharPress
from .transport import Action, State

if TYPE_CHECKING:
    from ..tuney import Tuney

# TODO: bg_color exists but is not useful, what is?
HOVER = {'hover_color': '#248060'}

REPLAY = {'text': 'Replay (Ctrl+R)', 'fg_color': '#30a870', **HOVER}
STOP = {'text': 'Stop (Ctrl+R)', 'fg_color': '#b0a8b0', **HOVER}
RANDOMIZE = {'text': 'Randomize', 'fg_color': '#707890', **HOVER}

QUEUE_POLL_IN_MS = 25
ICON_PATH = Path(__file__).resolve().parents[2] / 'icon.png'
CLEAR_ACCELERATOR = 'Command-B' if sys.platform == 'darwin' else 'Ctrl+B'
REFRESH_DEVICES_ACCELERATOR = 'Command-D' if sys.platform == 'darwin' else 'Ctrl+D'
SAVE_ACCELERATOR = 'Command-S' if sys.platform == 'darwin' else 'Ctrl+S'
UNDO_ACCELERATOR = 'Command-Z' if sys.platform == 'darwin' else 'Ctrl+Z'
REDO_ACCELERATOR = 'Command-Shift-Z' if sys.platform == 'darwin' else 'Ctrl+Y'
APP_NAME = 'Tuney'


def set_app_name(app: Misc) -> None:
    app.tk.call('tk', 'appname', APP_NAME)


class NoteLabel(BaseModel, frozen=True):
    labels: Sequence[str]
    on: bool = False

    @cached_property
    def text(self) -> str:
        return '\n'.join(self.labels)


class HistoryState(BaseModel, frozen=True):
    tuney: dict[str, object]
    recording_start_time: float | None
    recording_time_offset: float
    recording_insert_time: float | None
    replay_text: str
    loop_replay: bool
    loop_before: float
    loop_after: float
    loop_tempo: float
    randomize_on_each_loop: bool


class App(CTk):
    def __init__(self, tuney: Tuney) -> None:
        from .layout import Layout

        super().__init__(className=APP_NAME)
        set_app_name(self)
        self.title(APP_NAME)
        self._icon = PhotoImage(file=str(ICON_PATH))
        self.iconphoto(True, self._icon)
        self.tuney = tuney
        self.queue = Queue[CharPress]()
        n = len(tuney.note_labels)
        c = int(math.ceil(n**0.5))
        r = n // c
        r += n > (r * c)
        self.rows, self.columns = r, c
        self._is_replaying = False
        self._loop_replay = False
        self.loop_before = 0.0
        self.loop_after = 0.0
        self.loop_tempo = 1.0
        self.randomize_on_each_loop = False
        self._undo_stack: list[HistoryState] = []
        self._redo_stack: list[HistoryState] = []
        self._is_saving = False
        self._has_focus = True

        self.bind('<Activate>', self.on_activate)
        self.bind('<Deactivate>', self.on_deactivate)
        self.bind('<FocusIn>', self.on_activate)
        self.bind('<Control-r>', self.on_replay)
        self.bind('<Command-r>', self.on_replay)
        self.bind('<Control-b>', self.on_clear)
        self.bind('<Command-b>', self.on_clear)
        self.bind('<Control-s>', self.on_save)
        self.bind('<Command-s>', self.on_save)
        self.bind('<Control-d>', self.on_refresh_devices)
        self.bind('<Command-d>', self.on_refresh_devices)
        self.bind('<Control-z>', self.on_undo)
        self.bind('<Command-z>', self.on_undo)
        self.bind('<Control-y>', self.on_redo)
        self.bind('<Command-Shift-Z>', self.on_redo)
        self.configure(menu=self.menu)
        self.layout = Layout(self)

    def start(self) -> None:
        self._handle_queue()

    def destroy(self) -> None:
        self.tuney.player.close()
        super().destroy()

    def on_char(self, c: CharPress) -> None:
        if c.char:
            self.queue.put(c)

    def on_clear(self, *_) -> None:
        self.tuney.clear()

    def on_save(self, *_) -> None:
        self._is_saving = True
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension='.toml',
                filetypes=[
                    ('TOML', '*.toml'),
                    ('JSON', '*.json'),
                ],
            )
            if filename:
                self.tuney.save(Path(filename))
        finally:
            self._is_saving = False
            self._has_focus = False

    def on_transport_state(
        self, old_state: State, state: State, action: Action
    ) -> bool:
        filename = None
        if action == Action.save:
            self._is_saving = True
            try:
                filename = filedialog.asksaveasfilename(
                    defaultextension='.wav',
                    filetypes=[('WAV', '*.wav')],
                )
            finally:
                self._is_saving = False
                self._has_focus = False
        path = Path(filename) if filename else None
        return self.tuney.on_transport_state(old_state, state, action, path)

    def on_refresh_devices(self, *_) -> None:
        self.layout.refresh_devices()

    def on_randomize_timing(self, *_) -> None:
        self.tuney.randomize_timing()

    @property
    def is_saving(self) -> bool:
        return self._is_saving

    @property
    def has_focus(self) -> bool:
        return self._has_focus

    @property
    def focus_in_control_panel(self) -> bool:
        widget = self.focus_get()
        while widget is not None:
            if isinstance(widget, CTkEntry):
                return True
            if widget is self.layout.control_panel:
                return True
            widget = widget.master
        return False

    def on_activate(self, *_) -> None:
        self._has_focus = True

    def on_deactivate(self, *_) -> None:
        self._has_focus = False

    @cached_property
    def menu(self) -> Menu:
        menu = Menu(self)
        file_menu = Menu(menu, tearoff=False)
        edit_menu = Menu(menu, tearoff=False)
        edit_menu.add_command(
            label='Undo',
            accelerator=UNDO_ACCELERATOR,
            command=self.on_undo,
        )
        edit_menu.add_command(
            label='Redo',
            accelerator=REDO_ACCELERATOR,
            command=self.on_redo,
        )
        edit_menu.add_command(
            label='Randomize Timing',
            command=self.on_randomize_timing,
        )
        file_menu.add_command(
            label='Save',
            accelerator=SAVE_ACCELERATOR,
            command=self.on_save,
        )
        file_menu.add_command(
            label='Clear',
            accelerator=CLEAR_ACCELERATOR,
            command=self.on_clear,
        )
        file_menu.add_command(
            label='Refresh Devices',
            accelerator=REFRESH_DEVICES_ACCELERATOR,
            command=self.on_refresh_devices,
        )
        menu.add_cascade(label='File', menu=file_menu)
        menu.add_cascade(label='Edit', menu=edit_menu)
        return menu

    @property
    def is_replaying(self) -> bool:
        return self._is_replaying

    @is_replaying.setter
    def is_replaying(self, is_replaying: bool) -> None:
        if self._is_replaying != is_replaying:
            self._is_replaying = is_replaying
            self.layout.replay.configure(**(STOP if is_replaying else REPLAY))
            self.tuney.on_replay()

    def on_replay(self, *_) -> None:
        self.is_replaying = not self.is_replaying

    @property
    def loop_replay(self) -> bool:
        return self._loop_replay

    @loop_replay.setter
    def loop_replay(self, loop_replay: bool) -> None:
        if self._loop_replay != loop_replay:
            self._loop_replay = loop_replay
            self.layout.set_loop_state(loop_replay)

    def on_loop_replay(self, *_) -> None:
        self.record_undo()
        self.loop_replay = not self.loop_replay

    def on_loop_tempo(self, tempo: str) -> None:
        try:
            value = float(tempo)
        except ValueError:
            return
        if value > 0 and value != self.loop_tempo:
            self.record_undo()
            self.loop_tempo = value

    def on_loop_before(self, before: str) -> None:
        if (value := _float_or_none(before)) is not None and value != self.loop_before:
            self.record_undo()
            self.loop_before = value

    def on_loop_after(self, after: str) -> None:
        if (value := _float_or_none(after)) is not None and value != self.loop_after:
            self.record_undo()
            self.loop_after = value

    def on_randomize_on_each_loop(self, *_) -> None:
        self.record_undo()
        self.randomize_on_each_loop = not self.randomize_on_each_loop

    def record_undo(self) -> None:
        state = self._history_state()
        if not self._undo_stack or self._undo_stack[-1] != state:
            self._undo_stack.append(state)
        self._redo_stack.clear()

    def on_undo(self, *_) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(self._history_state())
        self._restore_history_state(self._undo_stack.pop())

    def on_redo(self, *_) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(self._history_state())
        self._restore_history_state(self._redo_stack.pop())

    def _history_state(self) -> HistoryState:
        return HistoryState(
            tuney=deepcopy(self.tuney.dump_data()),
            recording_start_time=self.tuney._recording_start_time,
            recording_time_offset=self.tuney._recording_time_offset,
            recording_insert_time=self.tuney._recording_insert_time,
            replay_text=self.tuney._replay_text,
            loop_replay=self.loop_replay,
            loop_before=self.loop_before,
            loop_after=self.loop_after,
            loop_tempo=self.loop_tempo,
            randomize_on_each_loop=self.randomize_on_each_loop,
        )

    def _restore_history_state(self, state: HistoryState) -> None:
        self.tuney.restore_data(state.tuney)
        self.tuney._recording_start_time = state.recording_start_time
        self.tuney._recording_time_offset = state.recording_time_offset
        self.tuney._recording_insert_time = state.recording_insert_time
        self.tuney._replay_text = state.replay_text
        self._loop_replay = state.loop_replay
        self.loop_before = state.loop_before
        self.loop_after = state.loop_after
        self.loop_tempo = state.loop_tempo
        self.randomize_on_each_loop = state.randomize_on_each_loop
        self.layout.set_text(self.tuney.display_text)
        self.layout.rebuild_control_panel()
        self.layout.rebuild_note_grid()
        self.layout.refresh_loop_controls()
        self.layout.set_loop_state(self.loop_replay)
        self.layout.set_randomize_on_each_loop_state(self.randomize_on_each_loop)

    def _handle_queue(self):
        while not self.queue.empty():
            self._on_char(self.queue.get())
        engine = self.tuney.player.__dict__.get('engine')
        if engine:
            for error in engine.diagnostics.take_errors():
                messagebox.showerror('Audio error', error, parent=self)
        self.after(QUEUE_POLL_IN_MS, self._handle_queue)

    def _on_char(self, c: CharPress) -> None:
        if frame := self.layout.note_buttons.get(c.char):
            frame.is_press = c.is_press


def _float_or_none(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None
