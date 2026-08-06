from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast

import tomlkit

from ..audio.mixer import NotePress
from ..config.serialize import serialize
from ..midi.file import MIDI_FILE_TICKS_PER_BEAT, is_midi_file, write_midi_file
from ..time.char_press import CharPress
from ..time.sequencer import Sequencer
from ..time.units import to_ms
from .app_state import AppState
from .platform_info import exit_with_message, report_error, trace

if TYPE_CHECKING:
    from .app import App


class AppPlayback(AppState):
    def on_char(self, c: CharPress) -> None:
        if not c.is_press and c.pressed_char and c.pressed_char == c.char.swapcase():
            c = CharPress(c.pressed_char, False, c.time)
        trace('char event', char=c.char, is_press=c.is_press)
        if c.char == '\b' and not c.is_press:
            self.stop_backspace_repeat()
        if self._is_listening:
            if c.char != '\b' or (c.is_press and self.char_presses):
                self.main_window.history.checkpoint_undo()
            recorded = self.key_recorder.recorded_char_press(
                c, self.char_presses, self.max_gap
            )
            if c.is_press:
                if c.char != '\b':
                    self.append_char_press(recorded)
                elif self.char_presses:
                    self.key_recorder.delete_last_char(self.char_presses)
                    self.start_backspace_repeat()
                self.main_window.update_text_display()
            else:
                if c.char != '\b':
                    self.append_char_press(recorded)
            self.play_char(c)

    def append_char_press(self, c: CharPress) -> None:
        self.char_presses.append(c)
        if len(self.char_presses) > 1 and c < (d := self.char_presses[-2]):
            report_error(f'Out-of-order char_press: {c} follows {d}')
            self.char_presses.sort()

    def start_backspace_repeat(self) -> None:
        self.stop_backspace_repeat()
        if self.backspace_repeat_delay >= 0 and self.backspace_repeat_rate > 0:
            self.key_recorder.backspace_repeat_after_id = self.main_window.after(
                round(to_ms(self.backspace_repeat_delay)),
                lambda: self.repeat_backspace(),
            )

    def repeat_backspace(self) -> None:
        self.key_recorder.backspace_repeat_after_id = None
        if not self._is_listening or not self.char_presses:
            return
        self.main_window.history.checkpoint_undo()
        self.key_recorder.delete_last_char(self.char_presses)
        self.main_window.update_text_display()
        self.play_char(CharPress('\b', time=0))
        if self.char_presses:
            self.key_recorder.backspace_repeat_after_id = self.main_window.after(
                round(1000 / self.backspace_repeat_rate),
                lambda: self.repeat_backspace(),
            )

    def stop_backspace_repeat(self) -> None:
        if self.key_recorder.backspace_repeat_after_id is not None:
            self.main_window.after_cancel(self.key_recorder.backspace_repeat_after_id)
            self.key_recorder.backspace_repeat_after_id = None

    def play_char(self, c: CharPress) -> None:
        if (note := self.mapper(c.char)) is not None:
            trace('play char', char=c.char, is_press=c.is_press, note=note)
            if not (
                self.midi.output.enable
                and self.midi.output.mute_audio_when_midi_enabled
            ):
                self.play_note(note, c.is_press)
            self.midi.output.send_note(note, c.is_press)
        if self.gui:
            self.main_window.on_char(c)

    def play_note(self, note: int, is_press: bool) -> None:
        trace('play note', is_press=is_press, note=note)
        if not self.silent:
            self.player.on_note(note, is_press)

    def on_replay(self) -> None:
        self.key_recorder.on_replay(cast('App', self))

    def replay_char_presses(self) -> list[CharPress]:
        char_presses = self._loop_window(
            self.replay_source_char_presses(),
            self.main_window.history.loop_before * 1000,
            self.main_window.history.loop_after * 1000,
        )
        if self.main_window.history.loop_tempo == 1:
            return char_presses
        return [
            CharPress(
                c.char,
                c.is_press,
                time=c.time / self.main_window.history.loop_tempo,
            )
            for c in char_presses
        ]

    def replay_source_char_presses(self) -> list[CharPress]:
        if (
            self.main_window.history.loop_replay
            and self.main_window.history.randomize_on_each_loop
        ):
            return list(self.text_timings.char_presses(self.display_text))
        return self.char_presses

    def stop_replaying(self) -> None:
        self.main_window.is_replaying = False

    def run_cli(self) -> None:
        if not self.char_presses:
            exit_with_message(
                'Required options were not provided: TEXT\n'
                'For full helptext, run tuney --help',
                2,
            )

        if self.silent and not self.output:
            exit_with_message('CLI mode requires sound')

        completed = False
        start_time = datetime.now(timezone.utc)

        def comment() -> str:
            return tomlkit.dumps(
                {
                    'original_text': self.display_text,
                    'recording_start_time': start_time.isoformat(),
                    'recording_finish_time': datetime.now(timezone.utc).isoformat(),
                    'settings': tomlkit.dumps(serialize(self.dump_data())),
                }
            )

        midi_file_output = self.output is not None and is_midi_file(self.output)
        try:
            if self.output and midi_file_output:
                write_midi_file(
                    self.output,
                    self.note_events(MIDI_FILE_TICKS_PER_BEAT),
                    self.midi.output,
                )
            elif self.output and self.silent:
                self.player.render_file(
                    self.output,
                    self.note_events(self.player.sample_rate),
                    comment,
                )
            else:
                if self.output:
                    self.player.start_recording(self.output, comment)
                self.play_cli()
            completed = True
        finally:
            if not (self.silent or midi_file_output):
                self.player.stop_all()
                self.player.wait()
                if self.output:
                    self.player.stop_recording()
                self.player.close()
            if self.output and not completed:
                self.output.unlink(missing_ok=True)

    def note_events(self, sample_rate: int) -> list[tuple[int, NotePress]]:
        events: list[tuple[int, NotePress]] = []
        for press in self.char_presses:
            if (note := self.mapper(press.char)) is not None:
                frame = round(press.time * sample_rate / 1000)
                events.append((frame, NotePress(note, press.is_press)))
        return events

    def output_comment(self) -> Callable[[], str]:
        start_time = datetime.now(timezone.utc)

        def comment() -> str:
            return tomlkit.dumps(
                {
                    'original_text': self.display_text,
                    'recording_start_time': start_time.isoformat(),
                    'recording_finish_time': datetime.now(timezone.utc).isoformat(),
                    'settings': tomlkit.dumps(serialize(self.dump_data())),
                }
            )

        return comment

    def play_cli(self) -> None:
        def callback(c: CharPress | None) -> None:
            if c:
                if c.is_press:
                    print(c.char, end='', flush=True)
                self.play_char(c)

        try:
            Sequencer(char_presses=self.char_presses, callback=callback).run()
        except KeyboardInterrupt:
            print()
            raise
        print()

    def _loop_window(
        self, char_presses: list[CharPress], loop_before: float, loop_after: float
    ) -> list[CharPress]:
        if not char_presses:
            return []

        start = max(0.0, loop_before)
        end = max(c.time for c in char_presses) - max(0.0, loop_after)
        prefix = max(0.0, -loop_before)
        suffix = max(0.0, -loop_after)

        result = [
            CharPress(c.char, c.is_press, time=c.time - start + prefix)
            for c in char_presses
            if start <= c.time <= end
        ]
        if result and suffix:
            result.append(CharPress(time=result[-1].time + suffix))
        return result
