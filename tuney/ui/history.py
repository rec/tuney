from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from PySide6.QtWidgets import QMessageBox
from reccy.configuration.units import Seconds
from reccy.configuration.update import validated_update

from ..app.key_recorder import KeyRecorder
from ..audio.player import Player
from ..presets.preset import restore_user_preset_snapshot, user_preset_snapshot
from ..time.char_press import CharPress

if TYPE_CHECKING:
    from .main_window import MainWindow


class LoopState(BaseModel, frozen=True):
    replay: bool = False
    before: Seconds = 0.0
    after: Seconds = 0.0
    tempo: float = Field(1.0, gt=0, allow_inf_nan=False)
    randomize_on_each_loop: bool = False


class WindowState(BaseModel, frozen=True):
    x: int
    y: int
    width: int
    height: int


class HistoryState(BaseModel, frozen=True):
    tuney: dict[str, object]
    key_recorder: KeyRecorder = Field(default_factory=KeyRecorder)
    loop: LoopState = Field(default_factory=LoopState)
    user_presets: dict[str, bytes | None] = Field(default_factory=dict)
    expected_user_presets: dict[str, bytes | None] = Field(default_factory=dict)


class TextEdit(BaseModel, frozen=True):
    index: int
    remove_count: int
    presses: list[CharPress]
    key_recorder: KeyRecorder


class History:
    def __init__(self, main_window: MainWindow) -> None:
        self.main_window = main_window
        self.loop_state = main_window.app.__dict__.pop(
            '_autosave_loop_state', LoopState()
        )
        self.undo_stack: list[HistoryState | TextEdit] = []
        self.redo_stack: list[HistoryState | TextEdit] = []

    @property
    def loop_replay(self) -> bool:
        return self.loop_state.replay

    @loop_replay.setter
    def loop_replay(self, loop_replay: bool) -> None:
        if self.loop_state.replay != loop_replay:
            self.loop_state = self.loop_state.model_copy(update={'replay': loop_replay})
            self.main_window.ui.set_loop_state(loop_replay)

    @property
    def loop_before(self) -> Seconds:
        return self.loop_state.before

    @loop_before.setter
    def loop_before(self, loop_before: Seconds) -> None:
        self.loop_state = self.loop_state.model_copy(update={'before': loop_before})

    @property
    def loop_after(self) -> Seconds:
        return self.loop_state.after

    @loop_after.setter
    def loop_after(self, loop_after: Seconds) -> None:
        self.loop_state = self.loop_state.model_copy(update={'after': loop_after})

    @property
    def loop_tempo(self) -> float:
        return self.loop_state.tempo

    @loop_tempo.setter
    def loop_tempo(self, loop_tempo: float) -> None:
        self.loop_state = validated_update(self.loop_state, ['tempo'], loop_tempo)

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
        self._restore_history(self.undo_stack, self.redo_stack)

    def redo(self, *_: object) -> None:
        self._restore_history(self.redo_stack, self.undo_stack)

    @contextmanager
    def text_edit(
        self, index: int = 0, recorder: KeyRecorder | None = None
    ) -> Iterator[None]:
        app = self.main_window.app
        before = [c.model_copy(deep=True) for c in app.char_presses[index:]]
        recorder = recorder if recorder is not None else self.recorder_state()
        try:
            yield
        finally:
            after = app.char_presses
            prefix = 0
            while (
                prefix < len(before)
                and index + prefix < len(after)
                and before[prefix] == after[index + prefix]
            ):
                prefix += 1
            end = len(before)
            after_end = len(after)
            while (
                end > prefix
                and after_end > index + prefix
                and before[end - 1] == after[after_end - 1]
            ):
                end -= 1
                after_end -= 1
            if (
                end != prefix
                or after_end != index + prefix
                or recorder != self.recorder_state()
            ):
                self.undo_stack.append(
                    TextEdit(
                        index=index + prefix,
                        remove_count=after_end - index - prefix,
                        presses=before[prefix:end],
                        key_recorder=recorder,
                    )
                )
                self.redo_stack.clear()

    def recorder_state(self) -> KeyRecorder:
        recorder = self.main_window.app.key_recorder
        return KeyRecorder(
            start_time=recorder.start_time,
            time_offset=recorder.time_offset,
            insert_time=recorder.insert_time,
            replay_text=recorder.replay_text,
        )

    @contextmanager
    def preset_edit(self, names: list[str]) -> Iterator[None]:
        state = self.state()
        before = user_preset_snapshot(names)
        try:
            yield
        finally:
            after = user_preset_snapshot(names)
            changed = [n for n in before if before[n] != after[n]]
            if changed:
                self.undo_stack.append(
                    state.model_copy(
                        update={
                            'user_presets': {n: before[n] for n in changed},
                            'expected_user_presets': {n: after[n] for n in changed},
                        }
                    )
                )
                self.redo_stack.clear()

    def clear_settings(self) -> None:
        self.checkpoint_undo()
        app = self.main_window.app
        data = type(app)().model_dump()
        data['gui'] = app.gui
        self.restore(HistoryState(tuney=data))

    def state(self) -> HistoryState:
        return HistoryState(
            tuney=deepcopy(self.main_window.app.dump_data()),
            key_recorder=self.recorder_state(),
            loop=self.loop_state,
        )

    def restore(self, state: HistoryState) -> None:
        window = self.main_window
        restore_user_preset_snapshot(state.user_presets, state.expected_user_presets)
        window.app.restore_data(state.tuney)
        self._restore_recorder(state.key_recorder)
        self.loop_state = state.loop
        window.update_text_display()
        window.ui.rebuild_control_panel()
        window.ui.rebuild_note_grid()
        window.ui.refresh_loop_controls()
        window.ui.set_loop_state(self.loop_replay)
        window.ui.set_randomize_on_each_loop_state(self.randomize_on_each_loop)
        if hasattr(window, 'load_autosave_action'):
            window.load_autosave_action.setChecked(window.app.load_autosave)
        if hasattr(window, 'show_text_timings_action'):
            window.show_text_timings_action.setChecked(window.app.show_text_timings)

    def _restore_history(
        self,
        source: list[HistoryState | TextEdit],
        destination: list[HistoryState | TextEdit],
    ) -> None:
        if not source:
            return
        state = source[-1]
        if isinstance(state, TextEdit):
            app = self.main_window.app
            try:
                if isinstance(player := app.__dict__.get('player'), Player):
                    player.close()
            except (OSError, ValueError) as error:
                QMessageBox.critical(self.main_window, 'Undo/Redo', str(error))
                return
            end = state.index + state.remove_count
            inverse_edit = TextEdit(
                index=state.index,
                remove_count=len(state.presses),
                presses=[
                    c.model_copy(deep=True) for c in app.char_presses[state.index : end]
                ],
                key_recorder=self.recorder_state(),
            )
            app.char_presses[state.index : end] = [
                c.model_copy(deep=True) for c in state.presses
            ]
            self._restore_recorder(state.key_recorder)
            source.pop()
            destination.append(inverse_edit)
            self.main_window.update_text_display()
            return
        inverse = self.state().model_copy(
            update={
                'user_presets': state.expected_user_presets,
                'expected_user_presets': state.user_presets,
            }
        )
        try:
            self.restore(state)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self.main_window, 'Undo/Redo', str(error))
            return
        source.pop()
        destination.append(inverse)

    def _restore_recorder(self, recorder: KeyRecorder) -> None:
        current = self.main_window.app.key_recorder
        current.start_time = recorder.start_time
        current.time_offset = recorder.time_offset
        current.insert_time = recorder.insert_time
        current.replay_text = recorder.replay_text
