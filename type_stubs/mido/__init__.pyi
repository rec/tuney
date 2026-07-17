from typing import Any

class Message:
    def __init__(
        self,
        type: str,
        *,
        channel: int = ...,
        note: int = ...,
        velocity: int = ...,
        **kwargs: Any,
    ) -> None: ...

def open_output(
    name: str | None = ...,
    virtual: bool = ...,
    autoreset: bool = ...,
    **kwargs: Any,
) -> Any: ...
def open_input(
    name: str | None = ...,
    virtual: bool = ...,
    callback: Any = ...,
    **kwargs: Any,
) -> Any: ...
def get_output_names() -> list[str]: ...
