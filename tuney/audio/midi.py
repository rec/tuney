import json
import subprocess
import sys
from functools import cached_property
from typing import Annotated, Any, cast

import mido
from pydantic import BaseModel

from ..tyro_option import tyro_option

ZERO_IS_NOTE_OFF = True
INTERNAL_LIST_MIDI_OUTPUTS = '--internal-list-midi-outputs'
MIDO_OUTPUT_NAMES_SCRIPT = (
    'import json, mido; print(json.dumps(mido.get_output_names()))'
)


class MIDI(BaseModel, frozen=True):
    # Enable MIDI output
    enable: Annotated[bool, tyro_option(name='midi-enable')] = False

    # MIDI output port name
    output: Annotated[
        str | None,
        tyro_option(name='midi-output'),
    ] = None

    # MIDI channel, from 0 to 15
    channel: Annotated[int, tyro_option(name='midi-channel')] = 0

    # Velocity used for MIDI note-on messages
    velocity: Annotated[int, tyro_option(name='midi-velocity')] = 0x40

    # Offset added to MIDI note numbers
    note_offset: Annotated[int, tyro_option(name='midi-note-offset')] = 0

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
    args = (
        [sys.executable, INTERNAL_LIST_MIDI_OUTPUTS]
        if getattr(sys, 'frozen', False)
        else [sys.executable, '-c', MIDO_OUTPUT_NAMES_SCRIPT]
    )
    try:
        result = subprocess.run(
            args,
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


def _output_names() -> list[str]:
    try:
        names = cast(Any, mido).get_output_names()
    except (OSError, RuntimeError) as error:
        print(f'Could not list MIDI outputs: {error}')
        return []
    return [name for name in names if isinstance(name, str)]


def output_names_json() -> str:
    return json.dumps(_output_names())
