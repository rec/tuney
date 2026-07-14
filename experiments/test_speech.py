import tempfile
from pathlib import Path

import pyttsx3


def save():
    path = Path(tempfile.gettempdir()) / 'tuney-test-speech.wav'
    engine = pyttsx3.init()
    print('zero')
    engine.save_to_file('Hello World', str(path))
    print('one')
    engine.runAndWait()
    print('two')


if __name__ == '__main__':
    save()
    # print(timeit.timeit(save, number=20))
