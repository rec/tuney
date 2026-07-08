from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ..recorders.key_recorder import KeyRecorder

if TYPE_CHECKING:
    from .main_window import MainWindow


class LoopState(BaseModel, frozen=True):
    replay: bool = False
    before: float = 0.0
    after: float = 0.0
    tempo: float = 1.0
    randomize_on_each_loop: bool = False


class HistoryState(BaseModel, frozen=True):
    tuney: dict[str, object]
    key_recorder: KeyRecorder = Field(default_factory=KeyRecorder)
    loop: LoopState = Field(default_factory=LoopState)


class History:
    def __init__(self, main_window: MainWindow) -> None:
        self.main_window = main_window
        self.loop_state = LoopState()
        self.undo_stack: list[HistoryState] = []
        self.redo_stack: list[HistoryState] = []

    @property
    def loop_replay(self) -> bool:
        return self.loop_state.replay

    @loop_replay.setter
    def loop_replay(self, loop_replay: bool) -> None:
        if self.loop_state.replay != loop_replay:
            self.loop_state = self.loop_state.model_copy(update={'replay': loop_replay})
            self.main_window.ui.set_loop_state(loop_replay)

    @property
    def loop_before(self) -> float:
        return self.loop_state.before

    @loop_before.setter
    def loop_before(self, loop_before: float) -> None:
        self.loop_state = self.loop_state.model_copy(update={'before': loop_before})

    @property
    def loop_after(self) -> float:
        return self.loop_state.after

    @loop_after.setter
    def loop_after(self, loop_after: float) -> None:
        self.loop_state = self.loop_state.model_copy(update={'after': loop_after})

    @property
    def loop_tempo(self) -> float:
        return self.loop_state.tempo

    @loop_tempo.setter
    def loop_tempo(self, loop_tempo: float) -> None:
        self.loop_state = self.loop_state.model_copy(update={'tempo': loop_tempo})

    @property
    def randomize_on_each_loop(self) -> bool:
        return self.loop_state.randomize_on_each_loop

    @randomize_on_each_loop.setter
    def randomize_on_each_loop(self, randomize_on_each_loop: bool) -> None:
        self.loop_state = self.loop_state.model_copy(
            update={'randomize_on_each_loop': randomize_on_each_loop}
        )

    def checkpoint_undo(self) -> None:
        state = self.state()
        if not self.undo_stack or self.undo_stack[-1] != state:
            self.undo_stack.append(state)
        self.redo_stack.clear()

    def undo(self, *_: object) -> None:
        if not self.undo_stack:
            return
        self.redo_stack.append(self.state())
        self.restore(self.undo_stack.pop())

    def redo(self, *_: object) -> None:
        if not self.redo_stack:
            return
        self.undo_stack.append(self.state())
        self.restore(self.redo_stack.pop())

    def clear_settings(self) -> None:
        self.checkpoint_undo()
        data = type(self.main_window.state.tuney)().model_dump()
        data['gui'] = self.main_window.state.tuney.gui
        self.restore(HistoryState(tuney=data))

    def state(self) -> HistoryState:
        return HistoryState(
            tuney=deepcopy(self.main_window.state.dump_data()),
            key_recorder=self.main_window.state.key_recorder.model_copy(deep=True),
            loop=self.loop_state,
        )

    def restore(self, state: HistoryState) -> None:
        window = self.main_window
        window.state.restore_data(state.tuney)
        window.state.key_recorder.start_time = state.key_recorder.start_time
        window.state.key_recorder.time_offset = state.key_recorder.time_offset
        window.state.key_recorder.insert_time = state.key_recorder.insert_time
        window.state.key_recorder.replay_text = state.key_recorder.replay_text
        self.loop_state = state.loop
        window.ui.set_text(window.state.display_text)
        window.ui.rebuild_control_panel()
        window.ui.rebuild_note_grid()
        window.ui.refresh_loop_controls()
        window.ui.set_loop_state(self.loop_replay)
        window.ui.set_randomize_on_each_loop_state(self.randomize_on_each_loop)
