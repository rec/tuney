import json
import subprocess
import sys
from collections.abc import Callable
from enum import StrEnum
from functools import cached_property
from typing import Annotated, Any

import mido
from pydantic import BaseModel, Field, field_validator

from ..app.platform_info import report_error
from ..config.display import Beginner, Display, Numeric, Options
from ..config.tyro_option import tyro_option

ZERO_IS_NOTE_OFF = True
INTERNAL_LIST_MIDI_OUTPUTS = '--internal-list-midi-outputs'
MIDO_OUTPUT_NAMES_SCRIPT = (
    'import json, mido; print(json.dumps(mido.get_output_names()))'
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
        report_error(f'Could not list MIDI outputs: {error}')
        return []
    if not isinstance(names, list):
        report_error(
            f'Could not list MIDI outputs: expected list, got {type(names).__name__}'
        )
        return []
    return [name for name in names if isinstance(name, str)]


class MIDIChannel(StrEnum):
    omni = 'omni'
    channel_1 = '1'
    channel_2 = '2'
    channel_3 = '3'
    channel_4 = '4'
    channel_5 = '5'
    channel_6 = '6'
    channel_7 = '7'
    channel_8 = '8'
    channel_9 = '9'
    channel_10 = '10'
    channel_11 = '11'
    channel_12 = '12'
    channel_13 = '13'
    channel_14 = '14'
    channel_15 = '15'
    channel_16 = '16'


class MIDIIn(BaseModel):
    # Enable MIDI input
    enable: Annotated[
        bool, tyro_option(name='midi-in-enable'), Beginner, Display(row=0)
    ] = False

    # MIDI input channel, or omni to receive all channels
    channel: Annotated[
        MIDIChannel,
        tyro_option(name='midi-in-channel', constructor=str),
        Beginner,
        Display(column=1, row=0),
        Options(lambda: [c.value for c in MIDIChannel]),
    ] = MIDIChannel.omni

    @field_validator('channel', mode='before')
    @classmethod
    def _validate_channel(cls, value: object) -> object:
        if value is None:
            return MIDIChannel.omni
        if isinstance(value, int):
            if value == 0:
                return MIDIChannel.omni
            if 1 <= value <= 16:
                return str(value)
        if isinstance(value, str):
            if value in {'', '0'}:
                return MIDIChannel.omni
            if value in MIDIChannel.__members__:
                return MIDIChannel[value]
        return value

    @property
    def mido_channel(self) -> int | None:
        return (
            None if self.channel is MIDIChannel.omni else int(self.channel.value) - 1
        )

    def accepts(self, message: Any) -> bool:
        return (channel := self.mido_channel) is None or getattr(
            message, 'channel', None
        ) == channel


class MidiOut(BaseModel):
    # Enable MIDI output
    enable: Annotated[
        bool, tyro_option(name='midi-enable'), Beginner, Display(row=0)
    ] = False

    # MIDI output port name
    output: Annotated[
        str | None,
        tyro_option(name='midi-output'),
        Beginner,
        Display(column=1, row=0, width=12),
        Options(output_names),
    ] = None

    # MIDI channel, from 0 to 15
    channel: Annotated[
        int,
        tyro_option(name='midi-channel'),
        Display(column=2, row=0),
        Numeric(width=2),
    ] = 0

    # Velocity used for MIDI note-on messages
    velocity: Annotated[
        int,
        tyro_option(name='midi-velocity'),
        Display(column=3, row=0),
        Numeric(width=2),
    ] = 0x40

    # Offset added to MIDI note numbers
    note_offset: Annotated[
        int,
        tyro_option(name='midi-note-offset'),
        Display(column=4, row=0),
        Numeric(width=2),
    ] = 0

    @cached_property
    def outport(self) -> Any:
        return mido.open_output(self.output)

    def midi_note(self, note_number: int) -> int:
        return (note_number + self.note_offset) % 128

    def tuney_note(self, note_number: int) -> int:
        return (note_number - self.note_offset) % 128

    def __call__(self, note_number: int, is_press: bool) -> None:
        if self.enable:
            self.outport.send(
                mido.Message(
                    channel=self.channel,
                    note=self.midi_note(note_number),
                    type='note_on' if is_press or ZERO_IS_NOTE_OFF else 'note_off',
                    velocity=max(0, min(127, is_press * self.velocity)),
                )
            )


class MIDI(BaseModel):
    # MIDI input settings
    input: MIDIIn = Field(default_factory=MIDIIn)

    # MIDI output settings
    output: MidiOut = Field(default_factory=MidiOut)

    def input_listener(
        self, callback: Callable[[int, bool], None]
    ) -> 'MIDIInputListener':
        return MIDIInputListener(self, callback)


class MIDIInputListener:
    def __init__(self, midi: MIDI, callback: Callable[[int, bool], None]) -> None:
        self.midi = midi
        self.callback = callback
        self.port: Any | None = None

    def start(self) -> None:
        if self.midi.input.enable and self.port is None:
            try:
                self.port = mido.open_input(callback=self.on_message)
            except (OSError, RuntimeError) as error:
                report_error(f'Could not open MIDI input: {error}')

    def close(self) -> None:
        if self.port is not None:
            self.port.close()
            self.port = None

    def on_message(self, message: Any) -> None:
        if not self.midi.input.accepts(message):
            return
        if message.type == 'note_on':
            self.callback(
                self.midi.output.tuney_note(message.note), message.velocity > 0
            )
        elif message.type == 'note_off':
            self.callback(self.midi.output.tuney_note(message.note), False)


def _output_names() -> list[str]:
    try:
        names = mido.get_output_names()
    except (OSError, RuntimeError) as error:
        report_error(f'Could not list MIDI outputs: {error}')
        return []
    return [name for name in names if isinstance(name, str)]


def output_names_json() -> str:
    return json.dumps(_output_names())
