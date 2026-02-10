from collections.abc import Callable
from typing import Any

type Milliseconds = float
type Seconds = float

type Frequency = float  # Must be non-negative
type NoteNumber = int  # May be negative

type Function = Callable[..., Any]
