from functools import cached_property
from typing import Any

import mido
from pydantic import BaseModel

ZERO_IS_NOTE_OFF = True


class MIDI(BaseModel, frozen=True):
    enable: bool = False
    output_name: str | None = None
    channel: int = 0
    velocity: int = 0x40
    note_offset: int = 0

    @cached_property
    def outport(self) -> Any:
        return mido.open_output(self.output_name)

    def __call__(self, note_number: int, is_press: bool) -> None:
        if self.enable:
            self.outport.send(
                mido.Message(
                    channel=self.channel,
                    note=(note_number + self.note_offset) % 128,
                    type='note_on' if is_press or ZERO_IS_NOTE_OFF else 'note_off',
                    velocity=max(0, min(127, is_press * self.velocity)),
                )
            )
