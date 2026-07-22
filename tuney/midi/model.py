from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from typing import Annotated, Literal

import mido
from pydantic import BaseModel, Field, field_validator

from ..app.platform_info import report_error
from ..config.display import Beginner, Display, Numeric, Options
from ..config.tyro_option import tyro_option
from .general_midi import general_midi_program_options

ZERO_IS_NOTE_OFF = True
CHANNELS = tuple(str(i + 1) for i in range(16))
MIDI_CHANNEL_OPTIONS = ['omni', *CHANNELS]


class MidiBase(BaseModel):
    # Enable MIDI
    enable: Annotated[bool, Beginner, Display(row=0)] = False

    # MIDI port name
    name: Annotated[
        str | None,
        Beginner,
        Display(column=1, row=0, width=12),
    ] = None

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
    def accepts(self, message: mido.Message) -> bool:
        return (channel := self.mido_channel) is None or getattr(
            message, 'channel', None
        ) == channel


class MidiOut(MidiBase):
    # MIDI output channel, or omni to use the default channel
    channel: Annotated[
        Literal['omni'] | Annotated[int, Field(ge=1, le=16)],
        Display(column=2, row=0),
        Options(lambda: MIDI_CHANNEL_OPTIONS),
    ] = 1

    # General MIDI instrument program
    program: Annotated[
        int,
        tyro_option(),
        Beginner,
        Display(column=3, row=0, width=24),
        Options(lambda: general_midi_program_options()),
    ] = Field(0, ge=0, le=127)

    # Velocity used for MIDI note-on messages
    velocity: Annotated[
        int,
        tyro_option(name='midi-velocity'),
        Display(column=4, row=0),
        Numeric(width=2),
    ] = 0x40

    # Offset added to MIDI note numbers
    note_offset: Annotated[
        int,
        tyro_option(name='midi-note-offset'),
        Display(column=5, row=0),
        Numeric(width=2),
    ] = 0

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


class MIDI(BaseModel):
    # MIDI input settings
    input: MIDIIn = Field(default_factory=MIDIIn)

    # MIDI output settings
    output: MidiOut = Field(default_factory=MidiOut)

    def listener(self, callback: Callable[[int, bool], None]) -> Listener:
        return Listener(self, callback)


class Listener:
    def __init__(self, midi: MIDI, callback: Callable[[int, bool], None]) -> None:
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


_OMNI = None, '', '0', 0, 'omni'
