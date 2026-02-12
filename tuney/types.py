from collections.abc import Callable
from fractions import Fraction
from typing import Any, TypeAlias

import numpy as np

type Milliseconds = float
type Seconds = float

Number: TypeAlias = int | float | np.floating | np.integer | Fraction
type Frequency = Number  # Must be non-negative
type NoteNumber = int  # May be negative

type Callback = Callable[[], Any]
type Function = Callable[..., Any]

type Data = np.ndarray
