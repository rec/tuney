from collections.abc import Callable
from typing import Any

import numpy as np

type Data = np.ndarray
type Function = Callable[..., Any]
type Number = int | float | np.floating | np.integer
