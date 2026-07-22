from collections import Counter
from collections.abc import Callable
from enum import StrEnum, auto
from functools import cache
from typing import Annotated

import tyro
from pydantic import BaseModel, PrivateAttr, field_validator

from ..app.platform_info import report_error
from ..config.annotations import Beginner, Hidden, Numeric, Options
from ..config.tyro_option import tyro_option


class _SoundDevice:
    def query_devices(self) -> list[dict[str, object]]:
        import sounddevice

        return [dict(device) for device in sounddevice.query_devices()]


sounddevice = _SoundDevice()


@cache
def device_names() -> list[str]:
    try:
        devices = sounddevice.query_devices()
    except (OSError, RuntimeError) as error:
        report_error(f'Could not list audio devices: {error}')
        return []
    output_devices: list[tuple[int, str]] = []
    for i, device in enumerate(devices):
        name = device.get('name')
        channels = device.get('max_output_channels', 0)
        if isinstance(name, str) and isinstance(channels, int) and channels > 0:
            output_devices.append((i, name))
    counts = Counter(name for _, name in output_devices)
    return [f'[{i}] {name}' if counts[name] > 1 else name for i, name in output_devices]


def output_device(device: int | str | None) -> int | str | None:
    if not isinstance(device, str):
        return device
    try:
        devices = sounddevice.query_devices()
    except (OSError, RuntimeError):
        return device
    matches = [
        i
        for i, item in enumerate(devices)
        if item.get('name') == device and _output_channels(item) > 0
    ]
    return matches[0] if len(matches) > 1 else device


def _output_channels(device: dict[str, object]) -> int:
    channels = device.get('max_output_channels', 0)
    return channels if isinstance(channels, int) else 0


class DType(StrEnum):
    # Eight-bit signed int
    int8 = auto()

    # Eight-bit unsigned int
    uint8 = auto()

    # Sixteen-bit signed int
    int16 = auto()

    # Thirty-two bit signed int
    int32 = auto()

    # Thirty-two bit signed float
    float32 = auto()


def dtype_names() -> list[str]:
    return [dtype.value for dtype in DType]


class Device(BaseModel):
    # Audio output sample rate, in frames per second
    sample_rate: Annotated[int | None, Beginner, Numeric(row=0, width=6)] = None

    # Audio output device name or index
    device: Annotated[
        int | str | None,
        tyro_option('-d', name='audio-device'),
        Beginner,
        Options(options=device_names, column=1, row=0),
    ] = None

    # Sample data type sent to the audio output device
    dtype: Annotated[
        DType | None, Options(options=dtype_names, column=2, row=0, width=8)
    ] = None

    channels: Annotated[tyro.conf.Suppress[int | None], Hidden, Numeric()] = None
    extra_settings: tyro.conf.Suppress[str | None] = None
    clip_off: tyro.conf.Suppress[bool | None] = None
    dither_off: tyro.conf.Suppress[bool | None] = None
    never_drop_input: tyro.conf.Suppress[bool | None] = None
    prime_output_buffers_using_stream_callback: tyro.conf.Suppress[bool | None] = None

    _change_callback: Callable[[], None] | None = PrivateAttr(None)

    @field_validator('device', mode='before')
    @classmethod
    def _validate_device(cls, value: object) -> object:
        if isinstance(value, str) and value.startswith('['):
            index, _, _ = value[1:].partition(']')
            if index.isdecimal():
                return int(index)
        return value

    def set_change_callback(self, callback: Callable[[], None]) -> None:
        assert self.__pydantic_private__ is not None
        self.__pydantic_private__['_change_callback'] = callback

    def notify_change(self) -> None:
        if self._change_callback:
            self._change_callback()
