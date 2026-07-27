from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from typing import TYPE_CHECKING, Annotated, Literal

import mido
from pydantic import BaseModel, Field, field_validator

from ..app.platform_info import report_error
from ..config.annotations import Beginner, Display, Numeric, Options
from .general_midi import general_midi_program_options
from .port import OutputPort
from .ports import midi_names
from .tuning_dump import tuning_dump

if TYPE_CHECKING:
    from ..scale.scale import Scale
    from ..scale.tuning import Tuning
    from .listener import MidiListener

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

    @cached_property
    def mido_channel(self) -> int | None:
        return None if self.channel == 'omni' else self.channel - 1


class MidiIn(MidiBase):
    # MIDI port name
    name: Annotated[
        str | None,
        Beginner,
        Options(options=lambda: midi_names()[0], column=1, row=0, width=12),
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
        Options(options=lambda: midi_names()[1], column=1, row=0, width=12),
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
    def port(self) -> mido.OutputPort | None:
        try:
            return OutputPort(name=self.name)()
        except (OSError, RuntimeError, SystemError) as error:
            self.enable = False
            report_error(f'Could not open MIDI output: {error}')

    def start(self) -> None:
        if self.enable:
            self.send_program_change()
            self.send_volume_change()

    def close(self) -> None:
        if 'port' in self.__dict__ and self.port:
            try:
                self.port.close()
            except Exception as error:
                report_error(f'Could not open MIDI output: {error}')
            del self.port

    def midi_note(self, note_number: int) -> int:
        return (note_number + self.note_offset) % 128

    def tuney_note(self, note_number: int) -> int:
        return (note_number - self.note_offset) % 128

    def message(self, message_type: str, time: int = 0, **kwargs) -> mido.Message:
        if self.mido_channel is not None:
            kwargs['channel'] = self.mido_channel
        return mido.Message(message_type, time=time, **kwargs)

    def send_message(self, message_type: str, time: int = 0, **kwargs) -> None:
        if self.port:
            self.port.send(self.message(message_type, time=time, **kwargs))

    def send_program_change(self, time: int = 0) -> None:
        if self.program is not None:
            self.send_message('program_change', program=self.program, time=time)

    def send_volume_change(self, time: int = 0) -> None:
        self.send_message('control_change', control=7, time=time, value=self.volume)

    def send_tuning_dump(self, scale: Scale, tuning: Tuning) -> None:
        if self.enable and self.send_tuning and self.port:
            self.port.send(tuning_dump(scale, tuning, self.note_offset))

    def send_note(
        self, note_number: int, is_press: bool, use_note_offs: bool = False
    ) -> None:
        if self.enable and self.port:
            t = 'note_on' if is_press or not use_note_offs else 'note_off'
            velocity = max(0, min(127, is_press * self.velocity))
            note = self.midi_note(note_number)
            self.send_message(t, note=note, velocity=velocity)


class Midi(BaseModel):
    # MIDI input settings
    input: MidiIn = Field(default_factory=MidiIn)

    # MIDI output settings
    output: MidiOut = Field(default_factory=MidiOut)

    def listener(self, callback: Callable[[int, bool], None]) -> MidiListener:
        from .listener import MidiListener

        return MidiListener(self, callback)
