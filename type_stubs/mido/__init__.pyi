from typing import Any

class Message:
    type: str
    channel: int
    control: int
    data: tuple[int, ...]
    note: int
    program: int
    value: int
    velocity: int

    def __init__(
        self,
        type: str,
        *,
        channel: int = ...,
        control: int = ...,
        data: list[int] | tuple[int, ...] = ...,
        note: int = ...,
        program: int = ...,
        time: int = ...,
        value: int = ...,
        velocity: int = ...,
        **kwargs: Any,
    ) -> None: ...

class MetaMessage:
    is_meta: bool
    def __init__(self, type: str, **kwargs: Any) -> None: ...

class MidiTrack(list[Message | MetaMessage]): ...

class MidiFile:
    ticks_per_beat: int
    tracks: list[MidiTrack]
    def __init__(
        self, filename: str | None = ..., *, ticks_per_beat: int = ...
    ) -> None: ...
    def save(self, filename: str | None = ...) -> None: ...

class InputPort:
    def close(self) -> None: ...

class OutputPort(InputPort):
    def send(self, message: Message) -> None: ...

def open_output(
    name: str | None = ...,
    virtual: bool = ...,
    autoreset: bool = ...,
    **kwargs: Any,
) -> OutputPort: ...
def open_input(
    name: str | None = ...,
    virtual: bool = ...,
    callback: Any = ...,
    **kwargs: Any,
) -> InputPort: ...
def get_input_names() -> list[str]: ...
def get_output_names() -> list[str]: ...
