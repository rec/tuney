from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from typing import Annotated, Literal

import mido
from pydantic import BaseModel, Field, field_validator

from ..app.platform_info import report_error
from ..config.annotations import Beginner, Display, Numeric, Options
from .general_midi import general_midi_program_options

ZERO_IS_NOTE_OFF = True
CHANNELS = tuple(str(i + 1) for i in range(16))
MIDI_CHANNEL_OPTIONS = ['omni', *CHANNELS]
OMNI = None, '', '0', 0, 'omni'


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
    def accepts(self, message: mido.Message) -> bool:
        return (
            self.mido_channel is None
            or getattr(message, 'channel', None) == self.mido_channel
        )


class MidiOut(MidiBase):
    # MIDI output channel, or omni to use the default channel
    channel: Annotated[
        Literal['omni'] | Annotated[int, Field(ge=1, le=16)],
        Options(options=lambda: MIDI_CHANNEL_OPTIONS, column=2, row=0),
    ] = 1

    # General MIDI instrument program
    program: Annotated[
        int,
        Beginner,
        Options(options=general_midi_program_options, column=3, row=0, width=24),
    ] = Field(0, ge=0, le=127)

    # Velocity used for MIDI note-on messages
    velocity: Annotated[int, Numeric(column=4, row=0, width=2)] = 0x40

    # Offset added to MIDI note numbers
    note_offset: Annotated[int, Numeric(column=5, row=0, width=2)] = 0

    # Mute synthesized audio when MIDI output is enabled
    mute_audio_when_midi_enabled: Annotated[
        bool, Beginner, Display(column=6, row=0)
    ] = True

    @field_validator('program', mode='before')
    @classmethod
    def _validate_program(cls, value: object) -> object:
        if isinstance(value, str):
            prefix, _, _ = value.partition(' ')
            if prefix.isdecimal():
                return int(prefix) - 1
        return value

    @cached_property
    def port(self) -> mido.OutputPort:
        port = mido.open_output(self.name)
        port.send(self.send_program_change())
        return port

    def midi_note(self, note_number: int) -> int:
        return (note_number + self.note_offset) % 128

    def tuney_note(self, note_number: int) -> int:
        return (note_number - self.note_offset) % 128

    def send_program_change(self, time: int = 0) -> mido.Message:
        kwargs = {} if self.mido_channel is None else {'channel': self.mido_channel}
        return mido.Message(
            **kwargs,
            program=self.program,
            time=time,
            type='program_change',
        )

    def __call__(self, note_number: int, is_press: bool) -> None:
        if self.enable:
            kwargs = {} if self.mido_channel is None else {'channel': self.mido_channel}
            self.port.send(
                mido.Message(
                    **kwargs,
                    note=self.midi_note(note_number),
                    type='note_on' if is_press or ZERO_IS_NOTE_OFF else 'note_off',
                    velocity=max(0, min(127, is_press * self.velocity)),
                )
            )


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
                self.port = mido.open_input(input.name, callback=self.on_message)
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
