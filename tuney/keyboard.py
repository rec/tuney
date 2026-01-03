from queue import Queue
import dataclasses as dc

from functools import cached_property, wraps
from pynput import keyboard
from typing import Any, Callable, Iterator, TypeAlias

OptionalKey: TypeAlias = keyboard.Key | keyboard.KeyCode | None


@dc.dataclass(frozen=True)
class KeyAction:
    char: str = ""
    is_press: bool = False

    def __bool__(self) -> bool:
        return bool(self.char)


@dc.dataclass
class KeyboardListener:
    action: Callable[[KeyAction], Any]

    @cached_property
    def listener(self) -> keyboard.Listener:
        return _make_listener(self)

    def on_press(self, key: OptionalKey) -> Any:
        return self._on(key, True)

    def on_release(self, key: OptionalKey) -> Any:
        return self._on(key, False)

    def join(self) -> None:
        with self.listener:
            try:
                self.listener.join()
            finally:
                self.action(KeyAction())

    def _on(self, key: OptionalKey, is_press: bool) -> Any:
        if char := getattr(key, "char", ""):
            return self.action(KeyAction(char, is_press))


class KeyboardQueue:
    @cached_property
    def queue(self) -> Queue[KeyAction]:
        return Queue()

    @cached_property
    def listener(self) -> KeyboardListener:
        return KeyboardListener(self.queue.put)

    def get_all(self) -> Iterator[KeyAction]:
        while key_action := self.queue.get():
            yield key_action
        yield KeyAction()

    def join(self) -> None:
        self.listener.join()


def _make_listener(kl: KeyboardListener) -> keyboard.Listener:
    listener = keyboard.Listener(on_press=kl.on_press, on_release=kl.on_release)
    log = getattr(listener, "_log", None)
    if not (log and hasattr(listener, "IS_TRUSTED")):
        return listener
    # Work around a bogus warning in pynput and Darwin
    BOGUS_WARNING = (
        "This process is not trusted! Input event monitoring will not be possible"
        " until it is added to accessibility clients."
    )
    warning_ = log.warning

    @wraps(warning_)
    def warning(a: str, *args: Any, **kwargs: Any) -> None:
        if not a.strip() or a.replace(BOGUS_WARNING, "").strip() or args or kwargs:
            warning_(a, *args, **kwargs)

    log.warning = warning
    return listener


if __name__ == "__main__":
    KeyboardListener(print).join()
