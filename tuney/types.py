from collections.abc import Callable
from typing import Any

type Milliseconds = float
type Seconds = float

SEC_IN_MS = 1000.0


def to_ms(s: Seconds) -> Milliseconds:
    return s * SEC_IN_MS


def to_seconds(m: Milliseconds) -> Seconds:
    return m / SEC_IN_MS


type Frequency = float  # Must be non-negative
type NoteNumber = int  # May be negative

type Callback = Callable[[], Any]
type Function = Callable[..., Any]
