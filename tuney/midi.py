import dataclasses as dc
from .note import NoteOctave

import mido


@dc.dataclass(frozen=True)
class NoteMaker:
    channel: int = 0
    velocity: int = 0x40
    zero_is_note_off: bool = True

    def __call__(self, note: NoteOctave, is_press: bool) -> mido.Message:
        return mido.Message(
            channel=self.channel,
            type="note_on" if is_press or self.zero_is_note_off else "note_off",
            velocity=is_press * self.velocity,
        )
