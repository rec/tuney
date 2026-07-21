from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from functools import cache, cached_property
from pathlib import Path
from typing import Annotated, Literal, Protocol

import mido
from pydantic import BaseModel, Field, field_validator

from ..app.platform_info import report_error
from ..config.display import Beginner, Display, Numeric, Options
from ..config.tyro_option import tyro_option
from .mixer import NotePress

ZERO_IS_NOTE_OFF = True
INTERNAL_LIST_MIDI_INPUTS = '--internal-list-midi-inputs'
INTERNAL_LIST_MIDI_OUTPUTS = '--internal-list-midi-outputs'
MIDO_INPUT_NAMES_SCRIPT = 'import json, mido; print(json.dumps(mido.get_input_names()))'
MIDO_OUTPUT_NAMES_SCRIPT = (
    'import json, mido; print(json.dumps(mido.get_output_names()))'
)
CHANNELS = tuple(str(i + 1) for i in range(16))
MIDI_CHANNEL_OPTIONS = 'omni', *CHANNELS
MIDI_FILE_SUFFIXES = {'.mid', '.midi', '.smf'}
MIDI_FILE_TEMPO = 1_000_000
MIDI_FILE_TICKS_PER_BEAT = 1000


class MIDIInputPort(Protocol):
    def close(self) -> None: ...


class MIDIOutputPort(MIDIInputPort, Protocol):
    def send(self, message: mido.Message) -> None: ...


def is_midi_file(path: Path) -> bool:
    return path.suffix.lower() in MIDI_FILE_SUFFIXES


def write_midi_file(
    path: Path, events: list[tuple[int, NotePress]], midi: MidiOut
) -> None:
    file = mido.MidiFile(ticks_per_beat=MIDI_FILE_TICKS_PER_BEAT)
    track = mido.MidiTrack()
    file.tracks.append(track)
    track.append(mido.MetaMessage('set_tempo', tempo=MIDI_FILE_TEMPO, time=0))
    previous = 0
    for frame, note in events:
        tick = max(0, round(frame))
        track.append(_midi_file_message(midi, note, tick - previous))
        previous = tick
    file.save(str(path))


def _midi_file_message(midi: MidiOut, note: NotePress, time: int) -> mido.Message:
    kwargs = {} if midi.mido_channel is None else {'channel': midi.mido_channel}
    return mido.Message(
        **kwargs,
        note=midi.midi_note(note.note_number),
        time=time,
        type='note_on' if note.is_press or ZERO_IS_NOTE_OFF else 'note_off',
        velocity=max(0, min(127, note.is_press * midi.velocity)),
    )


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


class MidiBase(BaseModel):
    # Enable MIDI
    enable: Annotated[bool, Beginner, Display(row=0)] = False

    # MIDI channel, or omni to use all channels
    channel: Annotated[
        Literal['omni'] | Annotated[int, Field(ge=1, le=16)],
        Display(column=2, row=0),
        Options(lambda: MIDI_CHANNEL_OPTIONS),
    ] = 'omni'

    @field_validator('channel', mode='before')
    @classmethod
    def _validate_channel(cls, value: object) -> Literal['omni'] | int:
        if isinstance(value, (int, str, type(None))) and not isinstance(value, bool):
            if value in _OMNI:
                return 'omni'
            if isinstance(value, int) and 1 <= value <= 16:
                return value
            if value in CHANNELS:
                return int(value)
        raise ValueError('MIDI channel must be omni, 0, or 1-16')

    @property
    def mido_channel(self) -> int | None:
        return None if self.channel == 'omni' else self.channel - 1


class MIDIIn(MidiBase):
    # MIDI input port name
    input: Annotated[
        str | None,
        tyro_option(name='midi-input'),
        Beginner,
        Display(column=1, row=0, width=12),
        Options(input_names),
    ] = None

    def accepts(self, message: mido.Message) -> bool:
        return (channel := self.mido_channel) is None or getattr(
            message, 'channel', None
        ) == channel


class MidiOut(MidiBase):
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
    def outport(self) -> MIDIOutputPort:
        return mido.open_output(self.output)

    def midi_note(self, note_number: int) -> int:
        return (note_number + self.note_offset) % 128

    def tuney_note(self, note_number: int) -> int:
        return (note_number - self.note_offset) % 128

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
    ) -> MIDIInputListener:
        return MIDIInputListener(self, callback)


class MIDIInputListener:
    def __init__(self, midi: MIDI, callback: Callable[[int, bool], None]) -> None:
        self.midi = midi
        self.callback = callback
        self.port: MIDIInputPort | None = None

    def start(self) -> None:
        if (input := self.midi.input).enable and self.port is None:
            try:
                self.port = mido.open_input(input, callback=self.on_message)
            except (OSError, RuntimeError) as error:
                report_error(f'Could not open MIDI input: {error}')

    def close(self) -> None:
        if self.port is not None:
            self.port.close()
            self.port = None

    def on_message(self, m: mido.Message) -> None:
        if self.midi.input.accepts(m) and m.type.startswith('note_'):
            is_on = m.type == 'note_on' and m.velocity > 0
            self.callback(self.midi.output.tuney_note(m.note), is_on)


def output_names_json() -> str:
    return _direct_port_names(mido.get_output_names, 'outputs')


def input_names_json() -> str:
    return _direct_port_names(mido.get_input_names, 'inputs')


def _direct_port_names(names: Callable[[], list[str]], kind: str) -> str:
    try:
        result = names()
    except (OSError, RuntimeError) as error:
        report_error(f'Could not list MIDI {kind}: {error}')
        result = []
    return json.dumps([name for name in result if isinstance(name, str)])


_OMNI = None, '', '0', 0, 'omni'
