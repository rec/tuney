from __future__ import annotations

import dataclasses as dc
import random
from collections.abc import Callable, Iterable, Iterator
from functools import cached_property, partial
from typing import Any

from pydantic import BaseModel

from ..keyboard.key_press import CharPress
from ..time import Sequencer
from ..types import Milliseconds
from .time_data import TimeData


class TextTimings(BaseModel, frozen=True):
    space: Milliseconds = 100
    period: Milliseconds = 300
    comma: Milliseconds = 200
    colon: Milliseconds = 400
    semicolon: Milliseconds = 400
    blank_line: Milliseconds = 1000

    overlap: Milliseconds = 20
    random_seed: int | None = None
    alpha_only: bool = True
    strip_accents: bool = True
    scale: float = 1.0

    other: dict[str, Milliseconds] = dc.field(default_factory=dict)
    timings: list[Milliseconds] | None = None

    @cached_property
    def timings_(self) -> list[Milliseconds]:
        return self.timings or _TIMINGS

    @cached_property
    def average_time(self) -> float:
        return sum(self.timings_) / len(self.timings_)

    @cached_property
    def random(self):
        return random.Random(self.random_seed)

    @cached_property
    def char_to_time(self) -> dict[str, Milliseconds]:
        return {v: getattr(self, k) for k, v in _CHARS.items()} | self.other

    def time_data(self, text: str) -> Iterator[TimeData[CharPress]]:
        time = 0
        chars = _strip_accents(text) if self.strip_accents else text
        for char in _filter_chars(chars):
            dt = self.char_to_time.get(char)
            if char.isalpha() or not (dt is None and self.alpha_only):
                dt = (dt or 0.0) + self.random.choice(self.timings_)
                begin = time * self.scale
                end = (time + dt) * self.scale
                yield TimeData(time=begin, data=CharPress(char, True))
                yield TimeData(time=end, data=CharPress(char, False))
                time += max(0, dt - self.overlap)

    @staticmethod
    def sequencer(
        s: str, callback: Callable[[CharPress | None], Any]
    ) -> Sequencer[CharPress]:
        timings = TextTimings()
        events = list(timings.time_data(s))
        assert s and events, (s, events)
        return Sequencer[CharPress](time_data=events, callback=callback)


def _filter_chars(it: Iterable[str]) -> Iterator[str]:
    # Filter out the first `\n', so each \n means an actual new line,
    # and any spaces after the first one.
    previous = ''
    for c in it:
        if not c.isspace():
            yield c
        elif c not in ' \n':
            continue
        elif c == '\n' == previous:
            yield c
        elif c == ' ' and previous not in ' \n':
            yield c
        previous = c


def _strip_accents(s: str) -> Iterator[str]:
    # https://stackoverflow.com/questions/517923/
    from unicodedata import category, normalize

    yield from (c for c in normalize('NFD', s) if category(c) != 'Mn')


_CHARS = {
    'space': ' ',
    'period': '.',
    'comma': ',',
    'colon': ':',
    'semicolon': ';',
    'blank_line': '\n',
}
_TIMINGS = (
    [56.04, 57.92, 60.35, 61.94, 62.54, 63.29, 63.32, 64.27, 66.26, 66.92]
    + [67.98, 68.02, 68.44, 69.33, 69.61, 70.61, 72.72, 72.75, 72.76, 73.42]
    + [75.07, 77.92, 78.52, 80.12, 83.55, 84.34, 85.13, 85.36, 85.47, 85.77]
    + [85.97, 86.32, 86.7, 88.45, 89.24, 89.26, 89.44, 89.54, 90.82, 91.18]
    + [91.22, 92.69, 92.94, 93.32, 94.24, 94.59, 94.75, 95.83, 96.64, 97.79]
    + [98.76, 99.11, 100.01, 100.38, 101.67, 103.73, 104.81, 104.87, 105.41, 106.56]
    + [107.5, 107.68, 107.97, 110.95, 111.07, 113.24, 115.18, 116.24, 116.24, 117.64]
    + [120.67, 122.09, 124.4, 125.88, 127.58, 128.57, 129.16, 130.85, 131.73, 133.19]
    + [133.81, 134.46, 136.04, 138.25, 140.16, 140.21, 140.22, 140.32, 141.9, 142.83]
    + [143.1, 148.71, 149.47, 149.88, 150.53, 153.21, 153.44, 153.66, 153.95, 156.17]
    + [157.75, 157.76, 158.17, 159.87, 160.48, 160.87, 160.97, 163.56, 164.12, 167.26]
    + [167.36, 168.21, 168.55, 169.04, 169.85, 169.86, 170.61, 171.43, 171.46, 172.9]
    + [173.78, 174.22, 174.76, 175.52, 176.18, 176.38, 176.49, 176.83, 178.75, 179.03]
    + [179.41, 180.81, 181.69, 182.37, 184.2, 184.48, 185.46, 185.9, 185.96, 187.05]
    + [188.67, 189.03, 190.0, 190.71, 192.68, 192.74, 192.88, 193.29, 194.49, 197.11]
    + [197.81, 199.08, 200.55, 200.66, 200.7, 201.65, 202.79, 203.32, 205.1, 205.7]
    + [206.18, 209.24, 210.69, 213.53, 214.09, 214.13, 222.19, 222.56, 222.58, 223.53]
    + [224.91, 227.26, 230.08, 234.93, 236.72, 246.01, 259.32, 260.27, 261.92, 266.67]
    + [269.42, 279.88, 287.71, 295.99, 299.94, 317.22, 329.73, 330.68, 357.17, 367.83]
    + [419.5, 422.63, 475.46, 521.2, 526.85, 594.64, 738.79]
)


def main():
    import sys

    msg = ' '.join(sys.argv[1:])
    callback = partial(print, end='', flush=True)
    TextTimings.sequencer(msg, callback).run()
    print()


if __name__ == '__main__':
    main()
