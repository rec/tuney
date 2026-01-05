import dataclasses as dc
from typing import TypeAlias

import numpy as np


@dc.dataclass
class DeviceConfig:
    channels: int = 1
    device: int | str = 0
    sample_rate: int = 48_000


Data: TypeAlias = np.ndarray
