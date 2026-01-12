import dataclasses as dc
from .note import Note

import mido

ZERO_IS_NOTE_OFF = True


@dc.dataclass(frozen=True)
class NoteMaker:
    channel: int = 0
    velocity: int = 0x40
    note_offset: int = 0

    def message(self, note: Note, is_press: bool) -> mido.Message:
        return mido.Message(
            channel=self.channel,
            note=(note.note_number + self.note_offset) % 128,
            type="note_on" if is_press or ZERO_IS_NOTE_OFF else "note_off",
            velocity=max(0, min(127, is_press * self.velocity)),
        )
