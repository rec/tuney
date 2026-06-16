from __future__ import annotations

from functools import cached_property

from customtkinter import CTkButton, CTkFrame, CTkLabel, CTkTextbox

from . import PAD, QUARTER
from .app import REPLAY, App, NoteLabel
from .note_button import NoteButton

TEXT_BOX_HEIGHT = 150
CONTROL_PANEL_HEIGHT = 100
FONT = 'Arial', 14

WIDTH, HEIGHT = 70, 80
NEW_CODE = True


class Layout:
    def __init__(self, app: App) -> None:
        width = WIDTH * app.columns
        height = HEIGHT * app.rows + TEXT_BOX_HEIGHT + CONTROL_PANEL_HEIGHT
        app.geometry(f'{width}x{height}')

        self.app = app
        _ = self.control_panel
        label = CTkLabel(self.stats_frame, text='Text:', font=(*FONT, 'bold'))
        label.pack(side='left')
        _ = self.textbox, self.note_buttons, self.replay

        self.set_text(app.tuney.display_text)

        for c in range(app.columns):
            self.note_grid.grid_columnconfigure(c, weight=1)
        for r in range(app.rows):
            self.note_grid.grid_rowconfigure(r, weight=1)

    def set_text(self, s: str) -> None:
        self.textbox.configure(state='normal')
        self.textbox.delete('1.0', 'end')
        self.textbox.insert('end', s)
        self.textbox.see('end')
        self.textbox.configure(state='disabled')
        self.count_label.configure(text=f'Chars: {len(s)}')

    @cached_property
    def control_panel(self) -> CTkFrame:
        f = CTkFrame(self.app, height=CONTROL_PANEL_HEIGHT)
        f.pack(
            fill='both',
            expand=False,
            padx=PAD,
            pady=PAD,
        )
        return f

    @cached_property
    def count_label(self) -> CTkLabel:
        cl = CTkLabel(self.stats_frame, text='Chars: 0', font=FONT)
        cl.pack(side='right')
        return cl

    @cached_property
    def note_buttons(self) -> dict[str, NoteButton]:
        it = self.app.tuney.note_labels.items()
        return {k: self._note_frame(i, k, n) for i, (k, n) in enumerate(it)}

    @cached_property
    def note_grid(self) -> CTkFrame:
        f = CTkFrame(self.app)
        f.pack(fill='both', expand=True, padx=PAD, pady=PAD)
        return f

    @cached_property
    def replay(self) -> CTkButton:
        f = CTkFrame(self.app, fg_color='transparent')
        f.pack(fill='x', padx=PAD, pady=(0, PAD))

        replay = CTkButton(f, command=self.app.on_replay, **REPLAY)  # ty:ignore[invalid-argument-type]
        replay.pack(side='right')
        return replay

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

    def _note_frame(self, i: int, char: str, nl: NoteLabel) -> NoteButton:
        r, c = divmod(i, self.app.columns)
        return NoteButton(
            self.note_grid,
            r,
            c,
            char,
            nl.text,
            self.app.tuney.on_char,
        )
