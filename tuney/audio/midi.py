import json
import subprocess
import sys
from collections.abc import Callable
from functools import cache, cached_property
from typing import Annotated, Any, Literal

import mido
from pydantic import BaseModel, Field, field_validator

from ..app.platform_info import report_error
from ..config.display import Beginner, Display, Numeric, Options
from ..config.tyro_option import tyro_option

ZERO_IS_NOTE_OFF = True
INTERNAL_LIST_MIDI_INPUTS = '--internal-list-midi-inputs'
INTERNAL_LIST_MIDI_OUTPUTS = '--internal-list-midi-outputs'
MIDO_INPUT_NAMES_SCRIPT = 'import json, mido; print(json.dumps(mido.get_input_names()))'
MIDO_OUTPUT_NAMES_SCRIPT = (
    'import json, mido; print(json.dumps(mido.get_output_names()))'
)
MIDI_CHANNEL_OPTIONS = ['omni', *[str(i) for i in range(1, 17)]]


@cache
def input_names() -> list[str]:
    return _port_names(INTERNAL_LIST_MIDI_INPUTS, MIDO_INPUT_NAMES_SCRIPT, 'inputs')


@cache
def output_names() -> list[str]:
    return _port_names(INTERNAL_LIST_MIDI_OUTPUTS, MIDO_OUTPUT_NAMES_SCRIPT, 'outputs')


def _port_names(internal_command: str, script: str, kind: str) -> list[str]:
    args = (
        [sys.executable, internal_command]
        if getattr(sys, 'frozen', False)
        else [sys.executable, '-c', script]
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
        report_error(f'Could not list MIDI {kind}: {error}')
        return []
    if not isinstance(names, list):
        report_error(
            f'Could not list MIDI {kind}: expected list, got {type(names).__name__}'
        )
        return []
    return [name for name in names if isinstance(name, str)]


class MIDIIn(BaseModel):
    # Enable MIDI input
    enable: Annotated[
        bool, tyro_option(name='midi-in-enable'), Beginner, Display(row=0)
    ] = False

    # MIDI input port name
    input: Annotated[
        str | None,
        tyro_option(name='midi-input'),
        Beginner,
        Display(column=1, row=0, width=12),
        Options(input_names),
    ] = None

    # MIDI input channel, or omni to receive all channels
    channel: Annotated[
        Literal['omni'] | Annotated[int, Field(ge=1, le=16)],
        tyro_option(name='midi-in-channel'),
        Beginner,
        Display(column=2, row=0),
        Options(lambda: MIDI_CHANNEL_OPTIONS),
    ] = 'omni'

    @field_validator('channel', mode='before')
    @classmethod
    def _validate_channel(cls, value: object) -> Literal['omni'] | int:
        return _validate_channel(value)

    @property
    def mido_channel(self) -> int | None:
        return None if self.channel == 'omni' else self.channel - 1

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

    # MIDI output channel, or omni to use the default channel
    channel: Annotated[
        Literal['omni'] | Annotated[int, Field(ge=1, le=16)],
        tyro_option(name='midi-channel'),
        Display(column=2, row=0),
        Options(lambda: MIDI_CHANNEL_OPTIONS),
    ] = 1

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

    @field_validator('channel', mode='before')
    @classmethod
    def _validate_channel(cls, value: object) -> Literal['omni'] | int:
        return _validate_channel(value)

    @property
    def mido_channel(self) -> int | None:
        return None if self.channel == 'omni' else self.channel - 1

    def __call__(self, note_number: int, is_press: bool) -> None:
        if self.enable:
            kwargs = {} if self.mido_channel is None else {'channel': self.mido_channel}
            self.outport.send(
                mido.Message(
                    **kwargs,
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
                self.port = mido.open_input(
                    self.midi.input.input, callback=self.on_message
                )
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
    return _direct_port_names(mido.get_output_names, 'outputs')


def _input_names() -> list[str]:
    return _direct_port_names(mido.get_input_names, 'inputs')


def output_names_json() -> str:
    return json.dumps(_output_names())


def input_names_json() -> str:
    return json.dumps(_input_names())


def _direct_port_names(names: Callable[[], object], kind: str) -> list[str]:
    try:
        result = names()
    except (OSError, RuntimeError) as error:
        report_error(f'Could not list MIDI {kind}: {error}')
        return []
    if not isinstance(result, list):
        return []
    return [name for name in result if isinstance(name, str)]


def _validate_channel(value: object) -> Literal['omni'] | int:
    if isinstance(value, bool):
        raise ValueError('MIDI channel must be omni, 0, or 1-16')
    if value is None or value == '' or value == '0' or value == 0:
        return 'omni'
    elif isinstance(value, int):
        if 1 <= value <= 16:
            return value
    elif isinstance(value, str):
        if value == 'omni':
            return 'omni'
        if value in {str(i) for i in range(1, 17)}:
            return int(value)
    raise ValueError('MIDI channel must be omni, 0, or 1-16')
