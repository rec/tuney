import numpy as np
from typing import Any, Callable, TypeAlias

Data: TypeAlias = np.ndarray
Function: TypeAlias = Callable[..., Any]
Number: TypeAlias = int | float | np.floating | np.integer
