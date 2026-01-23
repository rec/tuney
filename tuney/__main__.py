from typing import Any, Callable

from .audio.synth_player import OscillatorController
from .keyboard import KeyAction, KeyboardQueue
from .linear_mapper import LinearMapper
from .note_grid import NoteGrid, Text
from .scale import twelve_tet as tt


def main() -> None:
    mapper = LinearMapper(case_sensitive=True, invert=False)
    items = mapper.char_to_number.items()
    texts = {n: Text((tt.number_to_name(n), c)) for c, n in items}
    grid = NoteGrid(texts.values())

    oc = OscillatorController()

    def key_callback(k):
        if (note_number := mapper(k.char)) is not None:
            if k.is_press:
                oc.start(note_number)
            else:
                oc.stop(note_number)
            texts[note_number].on = k.is_press
            grid.render()

    kq = KeyboardQueue(key_callback)
    kq.start()
    kq.join()


if __name__ == "__main__":
    main()
