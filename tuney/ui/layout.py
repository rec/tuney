from __future__ import annotations

from typing import TYPE_CHECKING

from customtkinter import CTkButton, CTkFrame, CTkLabel, CTkTextbox

if TYPE_CHECKING:
    from .app import App

PAD = 20
QUARTER = PAD // 4
TEXT_BOX_HEIGHT = 150
FONT = ('Arial', 14)
BIG_FONT = ('Arial', 16, 'bold')

WIDTH, HEIGHT = 100, 150

REPLAY = {
    'text': 'Replay (Ctrl+R)',
    'fg_color': '#2fa572',
    'hover_color': '#248259',
}


def setup(app: App) -> tuple[CTkLabel, CTkTextbox]:
    app.title('Note app')

    width, height = WIDTH * app.columns, HEIGHT * app.rows
    app.geometry(f'{width}x{height}')
    _setup_notes(app)
    return _setup_controls(app)


def _setup_notes(app: App) -> None:
    from .app import RELEASED

    parent = CTkFrame(app)
    parent.pack(fill='both', expand=True, padx=PAD, pady=PAD)

    for i, (key, note_label) in enumerate(app.note_labels.items()):
        letter = '\n'.join(note_label.labels)

        r, c = divmod(i, app.columns)
        parent.grid_columnconfigure(c, weight=1)
        parent.grid_rowconfigure(r, weight=1)
        note = CTkFrame(
            parent,
            **RELEASED,  # ty: ignore[invalid-argument-type]
        )
        note.grid(row=r, column=c, padx=2 * QUARTER, pady=QUARTER, sticky='nsew')
        app.notes[key] = note

        label = CTkLabel(note, text=letter, font=BIG_FONT)
        label.pack(expand=True)


def _setup_controls(app: App) -> tuple[CTkLabel, CTkTextbox]:
    stats_frame = CTkFrame(app, fg_color='transparent')
    stats_frame.pack(fill='x', padx=PAD)

    label = CTkLabel(stats_frame, text='Text:', font=(*FONT, 'bold'))
    label.pack(side='left')

    count_label = CTkLabel(stats_frame, text='Chars: 0', font=FONT)
    count_label.pack(side='right')

    text = CTkTextbox(app, height=TEXT_BOX_HEIGHT, font=FONT)
    text.pack(fill='x', padx=PAD, pady=(QUARTER, 2 * QUARTER))
    text.configure(state='disabled')

    button_frame = CTkFrame(app, fg_color='transparent')
    button_frame.pack(fill='x', padx=PAD, pady=(0, PAD))

    replay_btn = CTkButton(
        button_frame,
        command=app.on_replay,
        **REPLAY,  # ty: ignore[invalid-argument-type]
    )
    replay_btn.pack(side='right')

    return count_label, text
