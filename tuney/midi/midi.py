from __future__ import annotations

import sys
from collections.abc import Callable
from functools import cached_property
from math import floor, log2
from typing import Annotated, Literal

import mido
from pydantic import BaseModel, Field, field_validator

from ..app.platform_info import report_error
from ..config.annotations import Beginner, Display, Numeric, Options
from ..scale.scale import Scale
from ..scale.tuning import Tuning
from .general_midi import general_midi_program_options
from .ports import input_names, output_names

ZERO_IS_NOTE_OFF = True
CHANNELS = tuple(str(i + 1) for i in range(16))
MIDI_CHANNEL_OPTIONS = ['omni', *CHANNELS]
OMNI = None, '', '0', 0, 'omni'
MTS_DEVICE_ID_ALL = 0x7F
MTS_SUB_ID = 0x08
MTS_BULK_DUMP = 0x01
MTS_TUNING_PROGRAM = 0
MTS_TUNING_NAME = 'Tuney'
MTS_NO_CHANGE = [0x7F, 0x7F, 0x7F]
MIDI_A4 = 69
A4_FREQUENCY = 440.0
SEMITONE_FRACTIONS = 16_384
VIRTUAL_MIDI_INPUT_NAME = 'Tuney MIDI In'
VIRTUAL_MIDI_OUTPUT_NAME = 'Tuney MIDI Out'


class MidiBase(BaseModel):
    # Enable MIDI
    enable: Annotated[bool, Beginner, Display(row=0)] = False

    # MIDI port name
    name: Annotated[str | None, Beginner, Display(column=1, row=0, width=12)] = None

    # MIDI channel, or omni to use all channels
    channel: Annotated[
        Literal['omni'] | Annotated[int, Field(ge=1, le=16)],
        Options(options=lambda: MIDI_CHANNEL_OPTIONS, column=2, row=0),
    ] = 'omni'

    @field_validator('channel', mode='before')
    @classmethod
    def _validate_channel(cls, value: object) -> Literal['omni'] | int:
        if isinstance(value, (int, str, type(None))) and not isinstance(value, bool):
            if value in OMNI:
                return 'omni'
            if isinstance(value, int) and 1 <= value <= 16:
                return value
            if value in CHANNELS:
                return int(value)
        raise ValueError('MIDI channel must be omni, 0, or 1-16')

    @property
    def mido_channel(self) -> int | None:
        return None if self.channel == 'omni' else self.channel - 1


class MidiIn(MidiBase):
    # MIDI port name
    name: Annotated[
        str | None,
        Beginner,
        Options(options=input_names, column=1, row=0, width=12),
    ] = None

    def accepts(self, message: mido.Message) -> bool:
        return (
            self.mido_channel is None
            or getattr(message, 'channel', None) == self.mido_channel
        )


class MidiOut(MidiBase):
    # MIDI port name
    name: Annotated[
        str | None,
        Beginner,
        Options(options=output_names, column=1, row=0, width=12),
    ] = None

    # MIDI output channel, or omni to use the default channel
    channel: Annotated[
        Literal['omni'] | Annotated[int, Field(ge=1, le=16)],
        Options(options=lambda: MIDI_CHANNEL_OPTIONS, column=2, row=0),
    ] = 1

    # General MIDI instrument program
    program: Annotated[
        int | None,
        Beginner,
        Options(options=general_midi_program_options, column=3, row=0, width=24),
    ] = Field(0, ge=0, le=127)

    # General MIDI channel volume
    volume: Annotated[int, Beginner, Numeric(column=4, row=0, width=3)] = Field(
        100, ge=0, le=127
    )

    # Velocity used for MIDI note-on messages
    velocity: Annotated[int, Numeric(column=5, row=0, width=2)] = 0x40

    # Offset added to MIDI note numbers
    note_offset: Annotated[int, Numeric(column=6, row=0, width=2)] = 0

    # Mute synthesized audio when MIDI output is enabled
    mute_audio_when_midi_enabled: Annotated[
        bool, Beginner, Display(column=7, row=0)
    ] = True

    # Send a MIDI Tuning Standard bulk tuning dump
    send_tuning: Annotated[bool, Display(column=8, row=0)] = False

    @field_validator('program', mode='before')
    @classmethod
    def _validate_program(cls, value: object) -> object:
        if value in (None, '', '(none)'):
            return None
        if isinstance(value, str):
            prefix, _, _ = value.partition(' ')
            if prefix.isdecimal():
                return int(prefix) - 1
        return value

    @cached_property
    def port(self) -> mido.OutputPort:
        port = mido.open_output(
            midi_port_name(self.name, VIRTUAL_MIDI_OUTPUT_NAME),
            virtual=use_virtual_midi_port(self.name),
        )
        if message := self.send_program_change():
            port.send(message)
        port.send(self.send_volume_change())
        return port

    def start(self) -> None:
        if self.enable:
            _ = self.port

    def close(self) -> None:
        if port := self.__dict__.pop('port', None):
            port.close()

    def midi_note(self, note_number: int) -> int:
        return (note_number + self.note_offset) % 128

    def tuney_note(self, note_number: int) -> int:
        return (note_number - self.note_offset) % 128

    def send_program_change(self, time: int = 0) -> mido.Message | None:
        if self.program is None:
            return None
        if self.mido_channel is None:
            return mido.Message(
                'program_change',
                program=self.program,
                time=time,
            )
        return mido.Message(
            'program_change',
            channel=self.mido_channel,
            program=self.program,
            time=time,
        )

    def send_volume_change(self, time: int = 0) -> mido.Message:
        if self.mido_channel is None:
            return mido.Message(
                'control_change',
                control=7,
                time=time,
                value=self.volume,
            )
        return mido.Message(
            'control_change',
            channel=self.mido_channel,
            control=7,
            time=time,
            value=self.volume,
        )

    def send_tuning_dump(self, scale: Scale, tuning: Tuning) -> None:
        if self.enable and self.send_tuning:
            self.port.send(self.tuning_dump(scale, tuning))

    def tuning_dump(self, scale: Scale, tuning: Tuning) -> mido.Message:
        name = _ascii_bytes(MTS_TUNING_NAME, 16)
        frequencies = [
            b
            for note in range(128)
            for b in _frequency_bytes(scale.frequency(tuning, self.tuney_note(note)))
        ]
        data = [
            0x7E,
            MTS_DEVICE_ID_ALL,
            MTS_SUB_ID,
            MTS_BULK_DUMP,
            MTS_TUNING_PROGRAM,
            *name,
            *frequencies,
        ]
        data.append(_tuning_checksum(data))
        return mido.Message('sysex', data=data)

    def __call__(self, note_number: int, is_press: bool) -> None:
        if self.enable:
            message_type = 'note_on' if is_press or ZERO_IS_NOTE_OFF else 'note_off'
            velocity = max(0, min(127, is_press * self.velocity))
            if self.mido_channel is None:
                message = mido.Message(
                    message_type, note=self.midi_note(note_number), velocity=velocity
                )
            else:
                message = mido.Message(
                    message_type,
                    channel=self.mido_channel,
                    note=self.midi_note(note_number),
                    velocity=velocity,
                )
            self.port.send(message)


class Midi(BaseModel):
    # MIDI input settings
    input: MidiIn = Field(default_factory=MidiIn)

    # MIDI output settings
    output: MidiOut = Field(default_factory=MidiOut)

    def listener(self, callback: Callable[[int, bool], None]) -> MidiListener:
        return MidiListener(self, callback)


class MidiListener:
    def __init__(self, midi: Midi, callback: Callable[[int, bool], None]) -> None:
        self.midi = midi
        self.callback = callback
        self.port: mido.InputPort | None = None

    def start(self) -> None:
        if (input := self.midi.input).enable and self.port is None:
            try:
                self.port = mido.open_input(
                    midi_port_name(input.name, VIRTUAL_MIDI_INPUT_NAME),
                    virtual=use_virtual_midi_port(input.name),
                    callback=self.on_message,
                )
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


def _ascii_bytes(text: str, length: int) -> list[int]:
    data = [ord(c) if 32 <= ord(c) <= 127 else ord(' ') for c in text[:length]]
    return data + [ord(' ')] * (length - len(data))


def midi_port_name(name: str | None, virtual_name: str) -> str | None:
    return virtual_name if use_virtual_midi_port(name) else name


def use_virtual_midi_port(name: str | None) -> bool:
    return name is None and (
        sys.platform == 'darwin' or sys.platform.startswith('linux')
    )


def _frequency_bytes(frequency: float) -> list[int]:
    if frequency <= 0:
        return list(MTS_NO_CHANGE)
    note = MIDI_A4 + 12 * log2(frequency / A4_FREQUENCY)
    semitone = floor(note)
    fraction = round((note - semitone) * SEMITONE_FRACTIONS)
    if fraction == SEMITONE_FRACTIONS:
        semitone += 1
        fraction = 0
    if not 0 <= semitone <= 127:
        return list(MTS_NO_CHANGE)
    return [semitone, fraction >> 7, fraction & 0x7F]


def _tuning_checksum(data: list[int]) -> int:
    checksum = 0
    for b in [data[0], data[1], *data[3:]]:
        checksum ^= b
    return checksum
