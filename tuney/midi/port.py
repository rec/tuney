from __future__ import annotations

import sys
from collections.abc import Callable
from functools import cached_property
from typing import ClassVar

import mido
from pydantic import BaseModel

VIRTUAL_ENABLED = sys.platform == 'darwin' or sys.platform.startswith('linux')
VIRTUAL_MIDI_INPUT_NAME = 'Tuney MIDI In'
VIRTUAL_MIDI_OUTPUT_NAME = 'Tuney MIDI Out'


class Port(BaseModel, frozen=True):
    name: str | None = None
    virtual_name: ClassVar[str] = ''

    @cached_property
    def is_virtual(self) -> bool:
        return VIRTUAL_ENABLED and self.name is None

    @cached_property
    def port_name(self) -> str | None:
        return self.virtual_name if self.is_virtual else self.name


class InputPort(Port, frozen=True):
    virtual_name: ClassVar[str] = VIRTUAL_MIDI_INPUT_NAME

    def __call__(
        self, callback: Callable[[mido.Message], None] | None = None
    ) -> mido.InputPort:
        return mido.open_input(
            self.port_name, virtual=self.is_virtual, callback=callback
        )


class OutputPort(Port, frozen=True):
    virtual_name: ClassVar[str] = VIRTUAL_MIDI_OUTPUT_NAME

    def __call__(self) -> mido.OutputPort:
        return mido.open_output(self.port_name, virtual=self.is_virtual)
