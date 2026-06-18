from collections.abc import Callable
from enum import StrEnum, auto
from functools import cache

import sounddevice
import tyro
from pydantic import BaseModel, PrivateAttr


class DType(StrEnum):
    int8 = auto()
    uint8 = auto()
    int32 = auto()
    int16 = auto()
    float32 = auto()


class Device(BaseModel, frozen=True):
    samplerate: int | None = None
    device: int | str | None = None
    dtype: DType | None = None

    blocksize: tyro.conf.Suppress[int | None] = None
    channels: tyro.conf.Suppress[int | None] = None
    latency: tyro.conf.Suppress[int | None] = None
    extra_settings: tyro.conf.Suppress[str | None] = None
    clip_off: tyro.conf.Suppress[bool | None] = None
    dither_off: tyro.conf.Suppress[bool | None] = None
    never_drop_input: tyro.conf.Suppress[bool | None] = None
    prime_output_buffers_using_stream_callback: tyro.conf.Suppress[bool | None] = None

    _change_callback: Callable[[], None] | None = PrivateAttr(None)

    def set_change_callback(self, callback: Callable[[], None]) -> None:
        assert self.__pydantic_private__ is not None
        self.__pydantic_private__['_change_callback'] = callback

    def notify_change(self) -> None:
        if self._change_callback:
            self._change_callback()


@cache
def device_names() -> list[str]:
    devices = sounddevice.query_devices()
    return [d['name'] for d in devices if int(d.get('max_output_channels', 0)) > 0]
