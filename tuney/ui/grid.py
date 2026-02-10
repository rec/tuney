import string
from collections.abc import Sequence
from queue import Queue
from typing import NamedTuple

from customtkinter import CTk, CTkButton, CTkFrame, CTkLabel, CTkTextbox
from pynput.keyboard import Key

from ..keyboard.modifiers import KeyPress
from ..keyboard.listener import KeyboardListener
from . import ColumnsRows, Text

# TODO: bg_color is not useful, what is?
PRESSED = {'fg_color': 'grey90', 'corner_radius': 8}
RELEASED = PRESSED | {'fg_color': 'gray60'}

REPLAY = {
    'text': 'Replay (Ctrl+R)',
    'fg_color': '#2fa572',
    'hover_color': '#248259',
}

PAD = 20
QUARTER = PAD // 4
TEXT_BOX_HEIGHT = 150
FONT = ('Arial', 14)
BIG_FONT = ('Arial', 16, 'bold')

QUEUE_POLL_IN_MS = 25
WIDTH, HEIGHT = 100, 150

KEYS = {Key.space: ' ', Key.enter: '\n', Key.backspace: '\b'}


class Note(NamedTuple):
    labels: Sequence[str]
    on: bool = False


class NoteGrid(CTk):
    def __init__(
        self,
        texts: dict[str, Text],
        update_entries: bool = True,
        add_listener: bool = True,
    ):
        super().__init__()
        self.texts = texts
        self.update_entries = update_entries
        self.char_count = 0
        self.queue = Queue[tuple[str, bool]]()
        self.notes = {}
        self.columns, self.rows = ColumnsRows.from_length(len(texts))

        self.title('Note grid')

        width, height = WIDTH * self.columns, HEIGHT * self.rows
        self.geometry(f'{width}x{height}')
        self._setup_grid()
        self._setup_controls()

        self.bind('<Control-r>', self.on_replay)
        self.bind('<Command-r>', self.on_replay)

        if add_listener:
            self.listener = KeyboardListener(self.on_key)
        else:
            self.listener = None

    def start(self) -> None:
        if self.listener:
            self.listener.start()
        self._handle_queue()

    def on_char(self, char: str, is_press: bool) -> None:
        self.queue.put((char, is_press))

    def on_key(self, k: KeyPress) -> None:
        if char := KEYS.get(k.key) or getattr(k.key, 'char', ''):
            self.on_char(char, k.is_press)

    def _handle_queue(self):
        while not self.queue.empty():
            char, is_press = self.queue.get()
            self._on_char(char, is_press)

        self.after(QUEUE_POLL_IN_MS, self._handle_queue)

    def _on_char(self, char: str, is_press: bool) -> None:
        if char in self.notes:
            self.notes[char].configure(**(PRESSED if is_press else RELEASED))
        if is_press:
            self.text.configure(state='normal')
            if char == '\b':
                self.char_count -= 1
                self.text.delete('end - 2c', 'end - 1c')
            else:
                self.char_count += 1
                self.text.insert('end', char)

            self.text.configure(state='disabled')
            self.text.see('end')
            self.count_label.configure(text=f'Chars: {self.char_count}')

    def _setup_grid(self):
        parent = CTkFrame(self)
        parent.pack(fill='both', expand=True, padx=PAD, pady=PAD)

        for i, (key, text) in enumerate(self.texts.items()):
            letter = '\n'.join(text.labels)

            r, c = divmod(i, self.columns)
            parent.grid_columnconfigure(c, weight=1)
            parent.grid_rowconfigure(r, weight=1)
            note = CTkFrame(
                parent,
                **RELEASED,  # ty: ignore[invalid-argument-type]
            )
            note.grid(row=r, column=c, padx=2 * QUARTER, pady=QUARTER, sticky='nsew')
            self.notes[key] = note

            label = CTkLabel(note, text=letter, font=BIG_FONT)
            label.pack(expand=True)

    def _setup_controls(self):
        stats_frame = CTkFrame(self, fg_color='transparent')
        stats_frame.pack(fill='x', padx=PAD)

        label = CTkLabel(stats_frame, text='Text:', font=(*FONT, 'bold'))
        label.pack(side='left')

        self.count_label = CTkLabel(stats_frame, text='Chars: 0', font=FONT)
        self.count_label.pack(side='right')

        self.text = CTkTextbox(self, height=TEXT_BOX_HEIGHT, font=FONT)
        self.text.pack(fill='x', padx=PAD, pady=(QUARTER, 2 * QUARTER))
        self.text.configure(state='disabled')

        button_frame = CTkFrame(self, fg_color='transparent')
        button_frame.pack(fill='x', padx=PAD, pady=(0, PAD))

        replay_btn = CTkButton(
            button_frame,
            command=self.on_replay,
            **REPLAY,  # ty: ignore[invalid-argument-type]
        )
        replay_btn.pack(side='right')

    def on_replay(self, _=None) -> None:
        print('on_replay')


def texts() -> dict[str, Text]:
    return {c: Text([c, c]) for c in string.ascii_lowercase}


if __name__ == '__main__':
    app = NoteGrid(texts())
    app.start()
