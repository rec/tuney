from __future__ import annotations

import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from .audio.multi_player import MultiPlayer
from .keyboard.char_press import CharPress
from .time import Milliseconds, Seconds, to_ms
from .time.sequencer import Sequencer
from .ui.transport import Action, State

if TYPE_CHECKING:
    from .tuney import Tuney


class KeyRecorder(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    sequencer: Sequencer | None = Field(default=None, exclude=True)
    recording_start_time: Seconds | None = None
    recording_time_offset: Milliseconds = 0.0
    recording_insert_time: Milliseconds | None = None
    replay_text: str = ''
    backspace_repeat_after_id: str | None = None

    def recorded_char_press(
        self,
        c: CharPress,
        char_presses: list[CharPress],
        max_gap_seconds: Seconds,
    ) -> CharPress:
        if self.recording_start_time is None and c.is_press:
            self.recording_start_time = c.time
        start = self.recording_start_time or c.time
        raw_time = to_ms(c.time - start)
        if self.recording_insert_time is not None and c.is_press and c.char != '\b':
            self.recording_time_offset = self.recording_insert_time - raw_time
            self.recording_insert_time = None
        recorded_time = raw_time + self.recording_time_offset
        max_gap = to_ms(max_gap_seconds)
        if max_gap > 0 and c.is_press and not self.recorded_notes_on(char_presses):
            time = char_presses[-1].time if char_presses else 0
            gap = recorded_time - time
            if gap > max_gap:
                self.recording_time_offset -= gap - max_gap
                recorded_time = raw_time + self.recording_time_offset
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
            self.recording_insert_time = deleted_time

    def on_replay(self, tuney: Tuney) -> None:
        tuney.player.stop_all()

        sequencer, self.sequencer = self.sequencer, None
        if sequencer:
            sequencer.stop()

        self.replay_text = ''
        if tuney.app.is_replaying:
            tuney.app.ui.set_text(self.replay_text)
            self.sequencer = Sequencer(
                char_presses=tuney._replay_char_presses(),
                callback=lambda c: self.on_replay_char(
                    c,
                    tuney._on_char,
                    lambda text: tuney.app.after(0, tuney.app.ui.set_text, text),
                    lambda: tuney.app.is_replaying,
                    lambda: tuney.app.after(0, self.finish_replay, tuney),
                ),
            )
            self.sequencer.start()
        else:
            tuney.app.ui.set_text(tuney.display_text)

    def on_replay_char(
        self,
        c: CharPress | None,
        play_char: Callable[[CharPress], None],
        schedule_text: Callable[[str], None],
        is_replaying: Callable[[], bool],
        schedule_finish: Callable[[], None],
    ) -> None:
        if c:
            if c.is_press:
                self.replay_text += c.char
                schedule_text(self.replay_text)
            play_char(c)
        elif is_replaying() and self.sequencer is not None:
            schedule_finish()

    def finish_replay(self, tuney: Tuney) -> None:
        if tuney.app.loop_replay and tuney._replay_char_presses():
            tuney.on_replay()
            return
        tuney.player.stop_all()
        tuney._stop_replaying()

    def clear(self) -> None:
        self.recording_start_time = None
        self.recording_time_offset = 0.0
        self.recording_insert_time = None
        self.replay_text = ''


class AudioRecorder(BaseModel):
    path: Path | None = None
    started: bool = False
    comment: Callable[[], str] | None = None

    def on_transport_state(
        self,
        old_state: State,
        state: State,
        action: Action,
        player: MultiPlayer,
        comment_factory: Callable[[], Callable[[], str]],
        path: Path | None = None,
    ) -> bool:
        if action == Action.save:
            if path is None:
                return False
            if old_state == State.recording:
                self.stop(player)
            self.save(path)
        elif action == Action.clear:
            if old_state == State.recording:
                self.stop(player)
            self.clear()
        elif state == State.paused:
            self.stop(player)
        else:
            self.start(player, comment_factory)
        return True

    def start(
        self, player: MultiPlayer, comment_factory: Callable[[], Callable[[], str]]
    ) -> None:
        if self.path is None:
            self.path = Path(tempfile.gettempdir()) / f'tuney-{uuid.uuid4()}.wav'
            self.path.touch()
            self.comment = comment_factory()
        assert self.path is not None
        player.start_recording(
            self.path,
            self.comment,
            append=self.started,
        )
        self.started = True

    def stop(self, player: MultiPlayer) -> None:
        player.stop_recording()

    def save(self, path: Path) -> None:
        if self.path is None:
            return
        self.path.replace(path)
        self._forget()

    def clear(self) -> None:
        if self.path is not None:
            self.path.unlink(missing_ok=True)
        self._forget()

    def _forget(self) -> None:
        self.path = None
        self.started = False
        self.comment = None
