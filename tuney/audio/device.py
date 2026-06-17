import tyro
from pydantic import BaseModel


class Device(BaseModel, frozen=True):
    samplerate: int | None = None
    blocksize: tyro.conf.Suppress[int | None] = None
    device: int | str | None = None
    channels: int | None = None
    dtype: str | None = None
    latency: tyro.conf.Suppress[int | None] = None
    extra_settings: tyro.conf.Suppress[str | None] = None
    clip_off: tyro.conf.Suppress[bool | None] = None
    dither_off: tyro.conf.Suppress[bool | None] = None
    never_drop_input: tyro.conf.Suppress[bool | None] = None
    prime_output_buffers_using_stream_callback: tyro.conf.Suppress[bool | None] = None
