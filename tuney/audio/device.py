from pydantic import BaseModel


class Device(BaseModel, frozen=True):
    samplerate: int | None = None
    blocksize: int | None = None
    device: int | str | None = None
    channels: int | None = None
    dtype: str | None = None
    latency: int | None = None
    extra_settings: str | None = None
    clip_off: bool | None = None
    dither_off: bool | None = None
    never_drop_input: bool | None = None
    prime_output_buffers_using_stream_callback: bool | None = None
