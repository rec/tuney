import io
from queue import Queue
import dataclasses as dc

from contextlib import redirect_stderr
from pynput import keyboard


@dc.dataclass
class KeyAction:
    char: str
    is_press: bool


@dc.dataclass
class Keyboard:
    queue: Queue[KeyAction] = dc.field(default_factory=Queue)

    def on_press(self, code: keyboard.KeyCode) -> None:
        self._append(code, True)

    def on_release(self, code: keyboard.KeyCode) -> None:
        self._append(code, False)

    def _append(self, code: keyboard.KeyCode,  is_press: bool) -> None:
        if char := getattr(code, "char", ""):
            self.queue.push(KeyAction(char, is_press))


def on_press(key):
    print(type(key), getattr(key, 'char', None))
    print(key)
    print(dir(key))
    print(*vars(key))

    try:
        print('alphanumeric key {0} pressed'.format(
            key.char))
    except AttributeError:
        print('special key {0} pressed'.format(
            key))

def on_release(key):
    print(type(key))
    print('{0} released'.format(
        key))
    if key == keyboard.Key.esc:
        # Stop listener
        return False

# Collect events until released
print('before')

li = keyboard.Listener(
        on_press=on_press,
        on_release=on_release
)
r = redirect_stderr(io.StringIO())
r.__enter__()

with li as listener:
    r.__exit__(None, None, None)
    print('middle')
    listener.join()
    print('after')
