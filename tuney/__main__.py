from threading import Thread
from typing import Any, Callable

from .audio.synth_player import OscillatorController
from .keyboard import KeyAction, KeyboardQueue
from .linear_mapper import LinearMapper
from .note_grid import NoteGrid, Text
from .scale import twelve_tet as tt

USE_GRID = not False


def main() -> None:
    mapper = LinearMapper(case_sensitive=True, invert=False)
    items = mapper.char_to_number.items()
    texts = {n: Text((tt.number_to_name(n), c)) for c, n in items}
    grid = NoteGrid(texts.values())

    oc = OscillatorController()

    def key_callback(k):
        if (note_number := mapper(k.char)) is not None:
            if oc.note(note_number, k.is_press):
                texts[note_number].on = k.is_press
                grid.redraw()

    kq = KeyboardQueue(key_callback)

    try:
        kq.start()
        if USE_GRID:
            grid.run()
    finally:
        kq.join()


if __name__ == "__main__":
    main()
