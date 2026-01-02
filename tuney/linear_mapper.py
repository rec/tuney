import dataclasses as dc
from functools import cached_property
from string import ascii_letters, ascii_lowercase
from typing import Iterable, Iterator, NamedTuple
from .note import Note


class LetterNote(NamedTuple):
    letter: str
    note: Note | None


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

    def __call__(self, letters: Iterable[str]) -> Iterator[LetterNote]:
        for letter in letters:
            yield LetterNote(letter, self._get(letter))

    def _get(self, letter: str) -> Note | None:
        assert len(letter) == 1, letter
        letter = letter if self.case_sensitive else letter.lower()
        try:
            index = self.alphabet.index(letter)
        except ValueError:
            return None
        if self.length:
            index = index % self.length
        return self.note.add(index)


if __name__ == "__main__":
    import sys

    mapper = LinearMapper(note_name="C4", case_sensitive=True)
    while line := input("... "):
        for letter, note in mapper(line):
            print(letter, note)

    s = " ".join(sys.argv[1:])
