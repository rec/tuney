from typing import Any, Callable, TypeAlias

import numpy as np

Data: TypeAlias = np.ndarray
Function: TypeAlias = Callable[..., Any]
Number: TypeAlias = int | float | np.floating | np.integer
