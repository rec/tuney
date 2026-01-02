import io
import sys
from queue import Queue
import dataclasses as dc

from contextlib import redirect_stderr
from functools import cached_property
from pynput import keyboard
from typing import TypeAlias

OptionalKey: TypeAlias = keyboard.Key | keyboard.KeyCode | None


@dc.dataclass
class KeyAction:
    char: str
    is_press: bool


@dc.dataclass
class Keyboard:
    queue: Queue[KeyAction] = dc.field(default_factory=Queue)

    def on_press(self, key: OptionalKey) -> None:
        self._append(key, True)

    def on_release(self, key: OptionalKey) -> None:
        self._append(key, False)

    @cached_property
    def listener(self) -> keyboard.Listener:
        return keyboard.Listener(on_press=self.on_press, on_release=self.on_release)

    def _append(self, key: OptionalKey, is_press: bool) -> None:
        print(key, is_press)
        if char := getattr(key, "char", ""):
            self.queue.put(KeyAction(char, is_press))

    def receive(self) -> None:
        r = redirect_stderr(s := io.StringIO())
        r.__enter__()

        with self.listener as listener:
            r.__exit__(None, None, None)
            if s.getvalue().replace(ERROR, "").strip():
                print(s.getvalue(), file=sys.stderr)
            listener.join()


ERROR = (
    "This process is not trusted! Input event monitoring will not be possible"
    " until it is added to accessibility clients."
)


def on_press(key):
    print(type(key), getattr(key, "char", None))
    print(key)
    print(dir(key))
    print(*vars(key))

    try:
        print("alphanumeric key {0} pressed".format(key.char))
    except AttributeError:
        print("special key {0} pressed".format(key))


def on_release(key):
    print(type(key))
    print("{0} released".format(key))
    if key == keyboard.Key.esc:
        # Stop listener
        return False


# Collect events until released
print("before")

if True:
    k = Keyboard().receive()

else:
    li = keyboard.Listener(on_press=on_press, on_release=on_release)
    r = redirect_stderr(io.StringIO())
    r.__enter__()

    with li as listener:
        r.__exit__(None, None, None)
        print("middle")
        listener.join()
        print("after")
