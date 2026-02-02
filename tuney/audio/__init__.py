from collections.abc import Callable
from typing import Any, TypeAlias

import numpy as np

Data: TypeAlias = np.ndarray
Function: TypeAlias = Callable[..., Any]
Number: TypeAlias = int | float | np.floating | np.integer
