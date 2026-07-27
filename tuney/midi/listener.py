from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import mido

from ..app.platform_info import report_error
from .port import InputPort

if TYPE_CHECKING:
    from .midi import Midi


class MidiListener:
    def __init__(self, midi: Midi, callback: Callable[[int, bool], None]) -> None:
        self.midi = midi
        self.callback = callback
        self.port: mido.InputPort | None = None

    def start(self) -> None:
        if (input := self.midi.input).enable and self.port is None:
            try:
                self.port = InputPort(name=input.name)(callback=self.on_message)
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
