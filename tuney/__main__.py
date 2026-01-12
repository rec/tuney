from .audio.file_player import FilePlayer
from .audio.synth_player import OscillatorController
from .keyboard import KeyboardQueue
from .linear_mapper import LinearMapper
from .note import Note

USE_FILE = not True


def main():
    mapper = LinearMapper(note_name="C2", case_sensitive=True, invert=False)
    oc = OscillatorController()

    def callback(key_action):
        for letter, note in mapper(key_action.char):
            if not isinstance(note, Note):
                continue
            elif not USE_FILE:
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
