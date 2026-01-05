from .audio.file_playback import FilePlayer
from .keyboard import KeyboardQueue
from .linear_mapper import LinearMapper


def main():
    mapper = LinearMapper(note_name="C3", case_sensitive=False, invert=False)

    def callback(key_action):
        if key_action.is_press:
            for letter, note in mapper(key_action.char):
                if note is not None:
                    print(note, "", end="", flush=True)
                    name = str(note).replace("♯", "#")
                    FilePlayer(f"assets/piano/{name}.mp3").run()

    kq = KeyboardQueue(callback)
    kq.start()


if __name__ == "__main__":
    main()
