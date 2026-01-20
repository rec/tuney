from typing import Any, Callable

from .audio.synth_player import OscillatorController
from .keyboard import KeyboardQueue
from .linear_mapper import LinearMapper

OC = OscillatorController()


def map_keyboard(callback: Callable[[int, bool], Any]) -> None:
    mapper = LinearMapper(case_sensitive=True, invert=False)

    def key_callback(k):
        if (note_number := mapper(k.char)) is not None:
            callback(note_number, k.is_press)

    KeyboardQueue(key_callback).start()


def synth(note_number: int, is_press: bool) -> None:
    if is_press:
        OC.start(note_number)
    else:
        OC.stop(note_number)


def main():
    map_keyboard(synth)


if __name__ == "__main__":
    main()
