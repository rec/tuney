from __future__ import annotations


from functools import cache
from typing import Iterator

from string import ascii_uppercase as UPPER


@cache
def count_scales(tones: int) -> tuple[str, ...]:
    if tones <= 0:
        return ()
    if tones == 1:
        return ("1",)
    if tones == 2:
        return ("11", "2")

    def count() -> Iterator[str]:
        yield from (f"1{i}" for i in count_scales(tones - 1))
        yield from (f"2{i}" for i in count_scales(tones - 2))

    return tuple(count())


def count_to_notes(s: str) -> str:
    if len(s) < 7:
        notes = "CDEFGA"[: len(s)]
    else:
        notes = UPPER[2 : len(s)] + "AB"

    def parts() -> Iterator[str]:
        for char, n in zip(s, notes):
            yield n
            if char == "2":
                yield "_"

    return "".join(parts())


if __name__ == "__main__":
    import sys

    _, *a = sys.argv
    count = int(a[0]) if a else 12

    for tones in range(count):
        it = (count_to_notes(i) for i in count_scales(tones + 1))
        print(tones + 1, *it, sep="\n    ")
