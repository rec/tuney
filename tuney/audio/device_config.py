import dataclasses as dc
from typing import Generic, TypeVar, get_args

import sounddevice as sd

_T = TypeVar('_T', bound=sd._StreamBase)


@dc.dataclass
class DeviceConfig:
    samplerate: int | None = None
    blocksize: int | None = None
    device: int | str | None = None
    channels: int | None = None
    dtype: type | None = None
    latency: int | None = None
    extra_settings: str | None = None
    clip_off: bool | None = None
    dither_off: bool | None = None
    never_drop_input: bool | None = None
    prime_output_buffers_using_stream_callback: bool | None = None


class DeviceMaker(Generic[_T]):
    @classmethod
    def type(cls) -> type[_T]:
        bases = getattr(cls, '__orig_bases__', None)
        assert bases is not None
        return get_args(bases[0])[0]

    def __call__(self, config: DeviceConfig) -> _T:
        return self.type()(**dc.asdict(config))


class OutputStreamMaker(DeviceMaker[sd.OutputStream]):
    pass


if __name__ == '__main__':
    print(OutputStreamMaker.type())
