import dataclasses as dc
from functools import cached_property
from string import ascii_letters, ascii_lowercase


@dc.dataclass(frozen=True)
class LinearMapper:
    alphabet_in: str | None = None
    length: int = 0
    case_sensitive: bool = False
    invert: bool = False
    offset: int = 0

    @cached_property
    def alphabet(self) -> str:
        if self.alphabet_in is None:
            return ascii_letters if self.case_sensitive else ascii_lowercase
        return self.alphabet_in

    def __call__(self, letter: str) -> int | None:
        if len(letter) > 1:
            return None

        letter = letter if self.case_sensitive else letter.lower()
        try:
            index = self.alphabet.index(letter)
        except ValueError:
            return None

        if self.invert:
            index = len(self.alphabet) - index - 1
        if self.length:
            index = index % self.length

        return index + self.offset
