from .audio.file_player import FilePlayer
from .audio.synth_player import OscillatorController
from .keyboard import KeyboardQueue
from .linear_mapper import LinearMapper
from .note import make_note, Note

USE_FILE = not True


def main():
    mapper = LinearMapper(case_sensitive=True, invert=False)
    note_name = make_note("C3")
    oc = OscillatorController()

    def callback(key_action):
        if (note_number := mapper(key_action.char)) is None:
            return
        note = note_name.add(note_number)
        assert isinstance(note, Note)
        if not USE_FILE:
            if key_action.is_press:
                oc.start(note)
            else:
                oc.stop(note)
        elif key_action.is_press:
            name = str(note).replace("♯", "#")
            FilePlayer(f"assets/piano/{name}.mp3").run()

    kq = KeyboardQueue(callback)
    kq.start()


if __name__ == "__main__":
    main()
