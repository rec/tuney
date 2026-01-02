import dataclasses as dc
from functools import cached_property
from string import ascii_letters, ascii_lowercase
from typing import Iterator
from .note import Note


@dc.dataclass(frozen=True)
class LinearMapper:
    input_alphabet: str = ""
    note_name: str = "C"
    length: int = 0
    case_sensitive: bool = False

    @cached_property
    def alphabet(self) -> str:
        return self.input_alphabet or (
            ascii_letters if self.case_sensitive else ascii_lowercase
        )

    @cached_property
    def note(self) -> Note:
        return Note.from_name(self.note_name)

    def __call__(self, letters: Iterator[str]) -> Iterator[Note]:
        for letter in letters:
            assert len(letter) == 1, letter
            letter = letter if self.case_sensitive else letter.lower()
            try:
                index = self.alphabet.index(letter)
            except ValueError:
                continue
            if self.length:
                index = index % self.length
            yield self.note.add(index)
