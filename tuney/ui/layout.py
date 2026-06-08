from __future__ import annotations

from functools import cached_property

from customtkinter import CTkButton, CTkFrame, CTkLabel, CTkTextbox

from .app import RELEASED, REPLAY, App, NoteLabel

PAD = 16
QUARTER = PAD // 4
TEXT_BOX_HEIGHT = 150
FONT = 'Arial', 14
BIG_FONT = 'Arial', 16, 'bold'

WIDTH, HEIGHT = 70, 100


class Layout:
    def __init__(self, app: App, text: str) -> None:
        self.app = app
        app.geometry(f'{WIDTH * app.columns}x{HEIGHT * app.rows}')
        app.title('Note app')
        self.set_text(text)
        _ = self.note_frames

        for c in range(app.columns):
            self.frame.grid_columnconfigure(c, weight=1)
        for r in range(app.rows):
            self.frame.grid_rowconfigure(r, weight=1)

        label = CTkLabel(self.stats_frame, text='Text:', font=(*FONT, 'bold'))
        label.pack(side='left')

    def get_text(self) -> str:
        return self.textbox.get('1.0', 'end-1c')

    def set_text(self, text: str) -> None:
        self.textbox.configure(state='normal')
        self.textbox.delete('1.0', 'end')
        self.append_string(text)

    def append_string(self, s: str) -> None:
        self.textbox.configure(state='normal')
        try:
            if s == '\b':
                self.textbox.delete('end - 2c', 'end - 1c')
            else:
                self.textbox.insert('end', s)
            self.textbox.see('end')
            self.count_label.configure(text=f'Chars: {len(self.get_text())}')
        finally:
            self.textbox.configure(state='disabled')

    @cached_property
    def frame(self) -> CTkFrame:
        f = CTkFrame(self.app)
        f.pack(fill='both', expand=True, padx=PAD, pady=PAD)
        return f

    @cached_property
    def stats_frame(self) -> CTkFrame:
        f = CTkFrame(self.app, fg_color='transparent')
        f.pack(fill='x', padx=PAD)
        return f

    @cached_property
    def textbox(self) -> CTkTextbox:
        t = CTkTextbox(self.app, height=TEXT_BOX_HEIGHT, font=FONT)
        t.pack(fill='x', padx=PAD, pady=(QUARTER, 2 * QUARTER))
        t.configure(state='disabled')
        return t

    @cached_property
    def count_label(self) -> CTkLabel:
        cl = CTkLabel(self.stats_frame, text='Chars: 0', font=FONT)
        cl.pack(side='right')
        return cl

    @cached_property
    def replay(self) -> CTkButton:
        f = CTkFrame(self.app, fg_color='transparent')
        f.pack(fill='x', padx=PAD, pady=(0, PAD))

        replay = CTkButton(f, command=self.app.on_replay, **REPLAY)  # ty:ignore[invalid-argument-type]
        replay.pack(side='right')
        return replay

    @cached_property
    def note_frames(self) -> dict[str, CTkFrame]:
        it = self.app.note_labels.items()
        return {k: self._note_frame(i, n) for i, (k, n) in enumerate(it)}

    def _note_frame(self, i: int, nl: NoteLabel) -> CTkFrame:
        r, c = divmod(i, self.app.columns)
        note_frame = CTkFrame(self.frame, **RELEASED)  # ty:ignore[invalid-argument-type]
        note_frame.grid(row=r, column=c, padx=2 * QUARTER, pady=QUARTER, sticky='nsew')

        label = CTkLabel(note_frame, text=nl.text, font=BIG_FONT)
        label.pack(expand=True)
        return note_frame
