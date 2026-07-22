from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from ..time import Milliseconds, Seconds, to_ms
from ..time.char_press import CharPress
from ..time.sequencer import Sequencer
from .platform_info import instrument

if TYPE_CHECKING:
    from .app import App


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
        if (
            (max_gap := to_ms(max_gap_seconds)) > 0
            and c.is_press
            and not self.recorded_notes_on(char_presses)
        ):
            time = char_presses[-1].time if char_presses else 0
            if (gap := recorded_time - time) > max_gap:
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
        instrument('key recorder delete last char', count=len(char_presses))
        deleted_time = None
        while char_presses:
            if (deleted := char_presses.pop()).is_press:
                deleted_time = deleted.time
                break
        if deleted_time is not None:
            self.insert_time = deleted_time

    def on_replay(self, state: App) -> None:
        from .app import play_char, replay_char_presses
        from .text_timing import text_timing_active_indexes

        instrument(
            'key recorder replay start',
            is_replaying=state.main_window.is_replaying,
        )
        state.player.stop_all()

        sequencer, self.sequencer = self.sequencer, None
        if sequencer:
            instrument('key recorder stop old sequencer')
            sequencer.stop()

        self.replay_text = ''
        if state.main_window.is_replaying:
            char_presses = replay_char_presses(state)
            instrument('key recorder replay events', count=len(char_presses))
            if state.use_speech and char_presses:
                text = ''.join(c.char for c in char_presses if c.is_press)
                duration = max(c.time for c in char_presses) / 1000
                state.player.start_speech(text, duration, state.speech_level)
            active_indexes = text_timing_active_indexes(char_presses)
            if state.show_text_timings:
                state.main_window.update_text_display()
                state.main_window.ui.set_active_text_timing(None)
            else:
                state.main_window.ui.set_text(self.replay_text)
                state.main_window.ui.set_play_cursor(0)

            def callback(char_press: CharPress | None) -> None:
                if char_press:
                    if state.show_text_timings:
                        state.main_window.after(
                            0,
                            state.main_window.ui.set_active_text_timing,
                            active_indexes.get(id(char_press)),
                        )
                    if char_press.is_press:
                        self.replay_text += char_press.char
                        if not state.show_text_timings:
                            state.main_window.after(
                                0, state.main_window.ui.set_text, self.replay_text
                            )
                            state.main_window.after(
                                0,
                                state.main_window.ui.set_play_cursor,
                                len(self.replay_text),
                            )
                    play_char(state, char_press)
                elif state.main_window.is_replaying and self.sequencer is not None:
                    state.main_window.after(0, self.finish_replay, state)

            self.sequencer = Sequencer(
                char_presses=char_presses,
                callback=callback,
            )
            instrument('key recorder sequencer start')
            self.sequencer.start()
        else:
            state.main_window.update_text_display()
            state.main_window.ui.set_play_cursor(None)
            state.main_window.ui.set_active_text_timing(None)
        instrument('key recorder replay end')

    def finish_replay(self, state: App) -> None:
        from .app import on_replay, replay_char_presses, stop_replaying

        instrument('key recorder finish replay')
        if state.main_window.history.loop_replay and replay_char_presses(state):
            on_replay(state)
            return
        state.player.stop_all()
        stop_replaying(state)

    def clear(self) -> None:
        instrument('key recorder clear')
        self.start_time = None
        self.time_offset = 0.0
        self.insert_time = None
        self.replay_text = ''
