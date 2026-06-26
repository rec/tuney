import json
import subprocess
import sys
from functools import cached_property
from typing import Annotated, Any

import mido
import tyro
from pydantic import BaseModel

ZERO_IS_NOTE_OFF = True
MIDO_OUTPUT_NAMES_SCRIPT = (
    'import json, mido; print(json.dumps(mido.get_output_names()))'
)


class MIDI(BaseModel, frozen=True):
    # Enable MIDI output
    enable: Annotated[
        bool, tyro.conf.arg(name='midi-enable', prefix_name=False)
    ] = False

    # MIDI output port name
    output: Annotated[
        str | None,
        tyro.conf.arg(name='midi-output', prefix_name=False),
    ] = None

    # MIDI channel, from 0 to 15
    channel: Annotated[
        int, tyro.conf.arg(name='midi-channel', prefix_name=False)
    ] = 0

    # Velocity used for MIDI note-on messages
    velocity: Annotated[
        int, tyro.conf.arg(name='midi-velocity', prefix_name=False)
    ] = 0x40

    # Offset added to MIDI note numbers
    note_offset: Annotated[
        int, tyro.conf.arg(name='midi-note-offset', prefix_name=False)
    ] = 0

    @cached_property
    def outport(self) -> Any:
        return mido.open_output(self.output)

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


def output_names() -> list[str]:
    try:
        result = subprocess.run(
            [sys.executable, '-c', MIDO_OUTPUT_NAMES_SCRIPT],
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
        names = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        print(f'Could not list MIDI outputs: {error}')
        return []
    if not isinstance(names, list):
        print(f'Could not list MIDI outputs: expected list, got {type(names).__name__}')
        return []
    return [name for name in names if isinstance(name, str)]
