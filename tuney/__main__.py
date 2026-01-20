from typing import Any, Callable

from .audio.file_player import FilePlayer
from .audio.synth_player import OscillatorController
from .keyboard import KeyboardQueue
from .linear_mapper import LinearMapper
from .note import make_note, Note

USE_FILE = not True
NOTE_NAME = make_note("C3")
OC = OscillatorController()


def map_keyboard(callback: Callable[[int, bool], Any]) -> None:
    mapper = LinearMapper(case_sensitive=True, invert=False)

    def key_callback(k):
        if (note_number := mapper(k.char)) is not None:
            callback(note_number, k.is_press)

    KeyboardQueue(key_callback).start()


def synth(note_number: int, is_press: bool) -> None:
    note = NOTE_NAME.add(note_number)
    assert isinstance(note, Note)
    cmd = OC.start if is_press else OC.stop
    cmd(note)


def file(note_number: int, is_press: bool) -> None:
    if is_press:
        note = NOTE_NAME.add(note_number)
        name = str(note).replace("♯", "#")
        FilePlayer(f"assets/piano/{name}.mp3").run()


def main():
    map_keyboard(file if USE_FILE else synth)


if __name__ == "__main__":
    main()
