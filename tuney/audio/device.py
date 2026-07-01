from collections.abc import Callable
from enum import StrEnum, auto
from functools import cache
from typing import Annotated, cast

import tyro
from pydantic import BaseModel, PrivateAttr

from ..tyro_option import tyro_option


class _SoundDevice:
    def query_devices(self) -> list[dict[str, object]]:
        import sounddevice

        return cast(list[dict[str, object]], sounddevice.query_devices())


sounddevice = _SoundDevice()


class DType(StrEnum):
    int8 = auto()
    uint8 = auto()
    int32 = auto()
    int16 = auto()
    float32 = auto()


class Device(BaseModel, frozen=True):
    # Audio output sample rate, in frames per second
    samplerate: Annotated[int | None, tyro_option()] = None

    # Audio output device name or index
    device: Annotated[
        int | str | None,
        tyro_option(name='audio-device', aliases=['-d']),
    ] = None

    # Sample data type sent to the audio output device
    dtype: Annotated[DType | None, tyro_option()] = None

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
    names: list[str] = []
    for device in devices:
        name = device.get('name')
        channels = device.get('max_output_channels', 0)
        if isinstance(name, str) and isinstance(channels, int) and channels > 0:
            names.append(name)
    return names
