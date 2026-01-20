import dataclasses as dc
from functools import cached_property
from string import ascii_letters, ascii_lowercase
from typing import Iterable, Iterator, NamedTuple
from .note import NoteName, make_note


class LetterNote(NamedTuple):
    letter: str
    note: NoteName | None


@dc.dataclass(frozen=True)
class LinearMapper:
    alphabet_in: str | None = None
    note: str = "C4"
    length: int = 0
    case_sensitive: bool = False
    invert: bool = False
    offset: int = 0

    @cached_property
    def alphabet(self) -> str:
        if self.alphabet_in is None:
            return ascii_letters if self.case_sensitive else ascii_lowercase
        return self.alphabet_in

    @cached_property
    def note_name(self) -> NoteName:
        return make_note(self.note)

    def __call__(self, letters: Iterable[str]) -> Iterator[LetterNote]:
        for letter in letters:
            yield LetterNote(letter, self.letter_to_note(letter))

    def letter_to_note(self, letter: str) -> NoteName | None:
        assert len(letter) == 1, letter
        letter = letter if self.case_sensitive else letter.lower()
        try:
            index = self.alphabet.index(letter)
        except ValueError:
            return None
        if self.invert:
            index = len(self.alphabet) - index - 1
        if self.length:
            index = index % self.length
        return self.note_name.add(index + self.offset)
