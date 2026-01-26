import dataclasses as dc
from functools import cached_property
from string import ascii_letters, ascii_lowercase


@dc.dataclass(frozen=True)
class LinearMapper:
    alphabet: str | None = None
    length: int = 0
    case_sensitive: bool = True
    invert: bool = False
    offset: int = 0

    def __call__(self, k: str) -> int | None:
        return self.char_to_number.get(k if self.case_sensitive else k.lower())

    @cached_property
    def char_to_number(self) -> dict[str, int]:
        if not (alphabet := self.alphabet):
            alphabet = ascii_letters if self.case_sensitive else ascii_lowercase

        def char_to_number(index: int, c: str) -> int:
            if self.invert:
                index = len(alphabet) - index - 1
            if self.length:
                index %= self.length
            return index + self.offset

        return {a: char_to_number(i, a) for i, a in enumerate(alphabet)}
