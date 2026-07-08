from typing import Annotated

from pydantic import BaseModel

from ..display import Beginner, Display
from ..tyro_option import tyro_option
from . import NoteNumber


class Root(BaseModel, frozen=True):
    #: The frequency of the reference `root_note`
    frequency: Annotated[
        float,
        tyro_option('-U', name='root-frequency'),
        Beginner,
        Display(column=4, row=0),
    ] = 440

    #: The note number of the reference note
    note: Annotated[
        NoteNumber,
        tyro_option('-W', name='root-note'),
        Beginner,
        Display(column=5, row=0),
    ] = 69  # MIDI note 69 is A440, for non-Yamaha units
