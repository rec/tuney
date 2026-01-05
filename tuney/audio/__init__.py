import dataclasses as dc


@dc.dataclass
class DeviceConfig:
    channels: int
    device: int | str
    sample_rate: int
