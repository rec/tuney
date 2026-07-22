from __future__ import annotations

from pathlib import Path
from typing import Annotated

import tyro
from pydantic import BaseModel, Field, field_validator

from ..audio.device import Device
from ..audio.sound import Sound
from ..mapper.mapper import Mapper
from ..midi.midi import Midi
from ..presets import preset_names
from ..scale.scale import Scale
from ..scale.tuning import Tuning
from ..time.char_press import CharPress
from ..time.sequencer import Sequencer
from ..time.text_timings import TextTimings
from .annotations import Beginner, General, Hidden, Numeric, Options
from .tyro_option import tyro_option


class Tuney(BaseModel):
    """
    Tuney is the top-level data representation for the tuny program

    Use positional `TEXT` to play characters as notes, then tune the scale,
    audio, MIDI, and timing from the same config model.
    """

    # Convert letters to scale indexes
    mapper: Mapper = Field(default_factory=Mapper)

    # Convert scale indexes to note names and note numbers
    scale: Scale = Field(default_factory=Scale)

    # Convert note numbers into frequencies
    tuning: Tuning = Field(default_factory=Tuning)

    # Audio output device settings
    device: Device = Field(default_factory=Device)

    # Synthesizer sound settings
    sound: Sound = Field(default_factory=Sound)

    # MIDI input and output settings
    midi: Midi = Field(default_factory=Midi)

    # Timings for playing back texts
    text_timings: TextTimings = Field(default_factory=lambda: TextTimings(scale=3.0))

    # Maximum silent gap to keep in recordings, in seconds
    max_gap: Annotated[
        float, tyro_option('-m'), General, Beginner, Numeric(min=0, max=4, inc=0.01)
    ] = 4.0

    # Time to hover over a widget before showing help, in seconds
    hover_time: Annotated[float, General, Numeric()] = 1.0

    # Time to hold backspace before it starts repeating, in seconds
    backspace_repeat_delay: Annotated[float, Hidden, Numeric()] = 2.0

    # Backspace repeats per second after backspace_repeat_delay
    backspace_repeat_rate: Annotated[float, Hidden, Numeric()] = 4.0

    # Load autosaved settings on startup
    load_autosave: Annotated[tyro.conf.Suppress[bool], Hidden] = True

    # Show recorded key timings instead of plain text
    show_text_timings: Annotated[tyro.conf.Suppress[bool], Hidden] = False

    # Temporarily play completed Scala browser entries before loading them
    audition_scala: Annotated[tyro.conf.Suppress[bool], Hidden] = True

    # Open the graphical interface
    gui: Annotated[bool, tyro_option('-g'), Hidden] = False

    # Disable synthesized audio output
    silent: Annotated[bool, tyro_option('-s'), General, Beginner] = False

    # Speak the replay text along with the synthesized notes
    use_speech: Annotated[bool, General, Beginner] = False

    # Speech volume multiplier
    speech_level: Annotated[
        float, General, Beginner, Numeric(min=0, max=4, inc=0.01)
    ] = 1.0

    # Audio file to write while playing text
    output: Annotated[Path | None, tyro_option('-o'), Hidden] = None

    # If True, listen to the keyboard even when other applications are in front
    run_in_background: Annotated[bool, tyro_option('-b'), General] = False

    # Named performance preset to load
    preset: Annotated[
        str | None,
        tyro_option('-p'),
        General,
        Beginner,
        Options(options=preset_names),
    ] = None

    # Load configs from a JSON or toml file
    config_file: Annotated[Path | None, tyro_option('-c'), Hidden] = None

    # Text to start the program with
    text: Annotated[
        str | list[CharPress] | None,
        tyro_option(
            '-t',
            constructor=str,
            help_behavior_hint='(optional)',
            metavar='TEXT',
        ),
        Hidden,
    ] = None

    # Text file to start the program with
    text_file: Annotated[tyro.conf.Suppress[Path | None], Hidden] = Field(
        default=None, exclude=True
    )

    # Positional text to start the program with
    text_args: Annotated[
        list[str],
        tyro.conf.Positional,
        tyro_option(name='text', metavar='TEXT'),
        Hidden,
    ] = Field(default_factory=list, exclude=True)

    @field_validator('text')
    @classmethod
    def _validate_text(
        cls, value: str | list[CharPress] | None
    ) -> str | list[CharPress] | None:
        if isinstance(value, list):
            Sequencer(char_presses=value, callback=lambda _: None)
        return value

    def model_post_init(self, __context: object) -> None:
        if self.text_args:
            self.text = ' '.join(self.text_args)
        if self.output:
            self.gui = False
