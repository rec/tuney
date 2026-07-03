from __future__ import annotations

from pathlib import Path
from typing import Annotated, final

import tyro
from pydantic import BaseModel, Field, field_validator

from .audio.midi import MIDI
from .audio.player import Player
from .display import Display
from .mapper.mapper import Mapper
from .presets import preset_names
from .time.char_press import CharPress
from .time.sequencer import Sequencer
from .time.text_timings import TextTimings
from .tyro_option import tyro_option


@final
class Tuney(BaseModel):
    """Turn text into music.

    Use positional `TEXT` to play characters as notes, then tune the scale,
    audio, MIDI, and timing from the same config model.
    """

    # Named performance preset to load
    preset: Annotated[
        str | None,
        tyro_option('-p'),
        Display(general=True, beginner=True, options=preset_names),
    ] = None

    # Load configs from a JSON or toml file
    config_file: Annotated[Path | None, tyro_option('-c'), Display(hidden=True)] = None

    # Map letters to notes
    mapper: Mapper = Mapper()

    # How to play back audio
    player: Player = Player()

    # How to send MIDI output
    midi: MIDI = MIDI()

    # Timings for playing back texts
    text_timings: TextTimings = TextTimings(scale=3.0)

    # Text to start the program with
    text: Annotated[
        str | list[CharPress] | None,
        tyro_option(
            '-t',
            constructor=str,
            help_behavior_hint='(optional)',
            metavar='TEXT',
        ),
        Display(hidden=True),
    ] = None

    # Text file to start the program with
    text_file: Annotated[
        tyro.conf.Suppress[Path | None],
        Display(hidden=True),
    ] = Field(default=None, exclude=True)

    # Positional text to start the program with
    text_args: Annotated[
        list[str],
        tyro.conf.Positional,
        tyro_option(name='text', metavar='TEXT'),
        Display(hidden=True),
    ] = Field(default_factory=list, exclude=True)

    # Maximum silent gap to keep in recordings, in seconds
    max_gap: Annotated[
        float,
        tyro_option('-m'),
        Display(general=True, beginner=True, step=0.01),
    ] = 4.0

    # Time to hover over a widget before showing help, in seconds
    hover_time: Annotated[float, Display(general=True)] = 1.0

    # Time to hold backspace before it starts repeating, in seconds
    backspace_repeat_delay: Annotated[float, Display(hidden=True)] = 2.0

    # Backspace repeats per second after backspace_repeat_delay
    backspace_repeat_rate: Annotated[float, Display(hidden=True)] = 4.0

    # Open the graphical interface
    gui: Annotated[bool, tyro_option('-g'), Display(hidden=True)] = False

    # Disable synthesized audio output
    silent: Annotated[bool, tyro_option('-s'), Display(general=True, beginner=True)] = (
        False
    )

    # Audio file to write while playing text
    output: Annotated[Path | None, tyro_option('-o'), Display(hidden=True)] = None

    # If True, listen to the keyboard even when other applications are in front
    run_in_background: Annotated[bool, tyro_option('-b'), Display(general=True)] = False

    # Path to the automatically saved GUI state
    autosave_file: tyro.conf.Suppress[Path | None] = Field(default=None, exclude=True)

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
            object.__setattr__(self, 'text', ' '.join(self.text_args))
        if self.output:
            object.__setattr__(self, 'gui', False)
