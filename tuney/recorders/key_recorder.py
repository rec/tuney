from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from ..time import Milliseconds, Seconds, to_ms
from ..time.char_press import CharPress
from ..time.sequencer import Sequencer

if TYPE_CHECKING:
    from ..tuney_state import TuneyState


class KeyRecorder(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    sequencer: Sequencer | None = Field(default=None, exclude=True)
    start_time: Seconds | None = None
    time_offset: Milliseconds = 0.0
    insert_time: Milliseconds | None = None
    replay_text: str = ''
    backspace_repeat_after_id: str | None = None

    def recorded_char_press(
        self,
        c: CharPress,
        char_presses: list[CharPress],
        max_gap_seconds: Seconds,
    ) -> CharPress:
        if self.start_time is None and c.is_press:
            self.start_time = c.time
            if char_presses and self.insert_time is None:
                self.time_offset = char_presses[-1].time
        start = self.start_time or c.time
        raw_time = to_ms(c.time - start)
        if self.insert_time is not None and c.is_press and c.char != '\b':
            self.time_offset = self.insert_time - raw_time
            self.insert_time = None
        recorded_time = raw_time + self.time_offset
        max_gap = to_ms(max_gap_seconds)
        if max_gap > 0 and c.is_press and not self.recorded_notes_on(char_presses):
            time = char_presses[-1].time if char_presses else 0
            gap = recorded_time - time
            if gap > max_gap:
                self.time_offset -= gap - max_gap
                recorded_time = raw_time + self.time_offset
        return CharPress(c.char, c.is_press, recorded_time)

    def recorded_notes_on(self, char_presses: list[CharPress]) -> set[str]:
        result = set()
        for c in char_presses:
            if c.is_press:
                result.add(c.char)
            else:
                result.discard(c.char)
        return result

    def delete_last_char(self, char_presses: list[CharPress]) -> None:
        deleted_time = None
        while char_presses:
            deleted = char_presses.pop()
            if deleted.is_press:
                deleted_time = deleted.time
                break
        if deleted_time is not None:
            self.insert_time = deleted_time

    def on_replay(self, state: TuneyState) -> None:
        state.tuney.player.stop_all()

        sequencer, self.sequencer = self.sequencer, None
        if sequencer:
            sequencer.stop()

        self.replay_text = ''
        if state.app.is_replaying:
            state.app.ui.set_text(self.replay_text)

            def callback(char_press: CharPress | None) -> None:
                if char_press:
                    if char_press.is_press:
                        self.replay_text += char_press.char
                        state.app.after(0, state.app.ui.set_text, self.replay_text)
                    state._on_char(char_press)
                elif state.app.is_replaying and self.sequencer is not None:
                    state.app.after(0, self.finish_replay, state)

            self.sequencer = Sequencer(
                char_presses=state._replay_char_presses(),
                callback=callback,
            )
            self.sequencer.start()
        else:
            state.app.ui.set_text(state.display_text)

    def finish_replay(self, state: TuneyState) -> None:
        if state.app.history.loop_replay and state._replay_char_presses():
            state.on_replay()
            return
        state.tuney.player.stop_all()
        state._stop_replaying()

    def clear(self) -> None:
        self.start_time = None
        self.time_offset = 0.0
        self.insert_time = None
        self.replay_text = ''
