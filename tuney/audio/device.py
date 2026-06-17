from collections.abc import Iterable
from enum import StrEnum, auto

import sounddevice
import tyro
from pydantic import BaseModel


class DType(StrEnum):
    int8 = auto()
    uint8 = auto()
    int32 = auto()
    int16 = auto()
    float32 = auto()


class Device(BaseModel, frozen=True):
    samplerate: int | None = None
    blocksize: tyro.conf.Suppress[int | None] = None
    device: int | str | None = None
    channels: int | None = None
    dtype: DType | None = None
    latency: tyro.conf.Suppress[int | None] = None
    extra_settings: tyro.conf.Suppress[str | None] = None
    clip_off: tyro.conf.Suppress[bool | None] = None
    dither_off: tyro.conf.Suppress[bool | None] = None
    never_drop_input: tyro.conf.Suppress[bool | None] = None
    prime_output_buffers_using_stream_callback: tyro.conf.Suppress[bool | None] = None


def output_device_names() -> list[str]:
    devices = sounddevice.query_devices()
    return _unique(
        device['name']
        for device in devices
        if int(device.get('max_output_channels') or 0) > 0
    )


def _unique(names: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(names))
