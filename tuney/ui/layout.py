from __future__ import annotations

from functools import cached_property

from customtkinter import CTkButton, CTkEntry, CTkFrame, CTkLabel, CTkSwitch, CTkTextbox

from . import constants
from .app import REPLAY, App, NoteLabel
from .control_panel import ControlPanel
from .note_button import NoteButton
from .transport import Transport

TEXT_BOX_HEIGHT = 120
CONTROL_PANEL_HEIGHT = 270
REPLAY_FRAME_HEIGHT = 43
LOOP_CONTROLS_HEIGHT = 28
FONT = 'Arial', 14

WIDTH, HEIGHT = 70, 80
NEW_CODE = True


class Layout:
    def __init__(self, app: App) -> None:
        width = WIDTH * app.columns
        height = (
            HEIGHT * app.rows
            + TEXT_BOX_HEIGHT
            + CONTROL_PANEL_HEIGHT
            + LOOP_CONTROLS_HEIGHT
        )
        app.geometry(f'{width}x{height}')

        self.app = app
        _ = self.control_panel
        label = CTkLabel(self.stats_frame, text='Text:', font=(*FONT, 'bold'))
        label.pack(side='left')
        _ = self.textbox, self.replay_frame, self.transport, self.replay, self.loop
        _ = self.loop_controls
        _ = self.note_buttons

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
    def control_panel(self) -> ControlPanel:
        frame = CTkFrame(self.app, fg_color='transparent')
        frame.pack(
            fill='both',
            expand=False,
            padx=constants.PAD,
            pady=constants.PAD,
        )
        f = ControlPanel(frame, self.app.tuney, CONTROL_PANEL_HEIGHT)
        f.pack(fill='both', expand=True)
        return f

    def refresh_devices(self) -> None:
        for option_control in self.control_panel.option_controls:
            option_control.refresh()

    def rebuild_control_panel(self) -> None:
        from .control_panel import rebuild_control_panel

        rebuild_control_panel(self.control_panel)

    def refresh_loop_controls(self) -> None:
        _set_entry_text(self.loop_before, str(self.app.loop_before))
        _set_entry_text(self.loop_after, str(self.app.loop_after))
        _set_entry_text(self.loop_tempo, str(self.app.loop_tempo))

    def set_loop_state(self, loop_replay: bool) -> None:
        if loop_replay:
            self.loop.select()
        else:
            self.loop.deselect()

    @cached_property
    def count_label(self) -> CTkLabel:
        cl = CTkLabel(self.stats_frame, text='Chars: 0', font=FONT)
        cl.pack(side='right')
        return cl

    @cached_property
    def note_buttons(self) -> dict[str, NoteButton]:
        it = self.app.tuney.note_labels.items()
        return {k: self._note_frame(i, k, n) for i, (k, n) in enumerate(it)}

    def rebuild_note_grid(self) -> None:
        self.app.tuney.__dict__.pop('note_labels', None)
        self.__dict__.pop('note_buttons', None)
        for child in self.note_grid.winfo_children():
            child.destroy()
        try:
            has_note_buttons = self.app.tuney.player.scale.note_count > 0
        except (AssertionError, ValueError, ZeroDivisionError):
            has_note_buttons = False
        if not has_note_buttons:
            return
        _ = self.note_buttons

    @cached_property
    def note_grid(self) -> CTkFrame:
        f = CTkFrame(self.app)
        f.pack(
            fill='both',
            expand=True,
            padx=constants.PAD,
            pady=constants.PAD - 8,
        )
        return f

    @cached_property
    def replay_frame(self) -> CTkFrame:
        f = CTkFrame(
            self.app,
            height=REPLAY_FRAME_HEIGHT,
            fg_color='transparent',
        )
        f.pack(fill='x', padx=constants.PAD)
        f.pack_propagate(False)
        return f

    @cached_property
    def transport(self) -> Transport:
        transport = Transport(
            self.replay_frame,
            self.app.on_transport_state,
            lambda: self.app.tuney.hover_time,
        )
        transport.pack(side='left')
        return transport

    @cached_property
    def replay(self) -> CTkButton:
        replay = CTkButton(
            self.replay_frame,
            height=REPLAY_FRAME_HEIGHT,
            font=('Arial', 18),
            command=self.app.on_replay,
            **REPLAY,  # ty:ignore[invalid-argument-type]
        )
        replay.place(relx=0.5, rely=0.5, anchor='center')
        return replay

    @cached_property
    def loop(self) -> CTkSwitch:
        loop = CTkSwitch(
            self.replay_frame,
            text='Loop',
            width=74,
            height=REPLAY_FRAME_HEIGHT,
            switch_width=36,
            switch_height=18,
            font=('Arial', 14),
            command=self.app.on_loop_replay,
            progress_color='#30a870',
            fg_color='#707890',
        )
        loop.pack(side='right')
        return loop

    @cached_property
    def loop_controls(self) -> CTkFrame:
        frame = CTkFrame(self.app, height=LOOP_CONTROLS_HEIGHT, fg_color='transparent')
        frame.pack(fill='x', padx=constants.PAD, pady=(2, 0))
        frame.pack_propagate(False)

        CTkLabel(frame, text='Before', font=FONT).pack(side='left', padx=(0, 4))
        self.loop_before = CTkEntry(frame, width=48, font=FONT)
        self.loop_before.insert(0, str(self.app.loop_before))
        self.loop_before.pack(side='left', padx=(0, 8))
        self.loop_before.bind(
            '<FocusOut>',
            lambda _: self.app.on_loop_before(self.loop_before.get()),
            add='+',
        )
        self.loop_before.bind(
            '<Return>',
            lambda _: self.app.on_loop_before(self.loop_before.get()),
            add='+',
        )

        CTkLabel(frame, text='After', font=FONT).pack(side='left', padx=(0, 4))
        self.loop_after = CTkEntry(frame, width=48, font=FONT)
        self.loop_after.insert(0, str(self.app.loop_after))
        self.loop_after.pack(side='left', padx=(0, 8))
        self.loop_after.bind(
            '<FocusOut>',
            lambda _: self.app.on_loop_after(self.loop_after.get()),
            add='+',
        )
        self.loop_after.bind(
            '<Return>',
            lambda _: self.app.on_loop_after(self.loop_after.get()),
            add='+',
        )

        CTkLabel(frame, text='Tempo', font=FONT).pack(side='left', padx=(0, 4))
        self.loop_tempo = CTkEntry(frame, width=48, font=FONT)
        self.loop_tempo.insert(0, str(self.app.loop_tempo))
        self.loop_tempo.pack(side='left')
        self.loop_tempo.bind(
            '<FocusOut>',
            lambda _: self.app.on_loop_tempo(self.loop_tempo.get()),
            add='+',
        )
        self.loop_tempo.bind(
            '<Return>',
            lambda _: self.app.on_loop_tempo(self.loop_tempo.get()),
            add='+',
        )
        return frame

    @cached_property
    def stats_frame(self) -> CTkFrame:
        f = CTkFrame(self.app, fg_color='transparent')
        f.pack(fill='x', padx=constants.PAD)
        return f

    @cached_property
    def textbox(self) -> CTkTextbox:
        t = CTkTextbox(self.app, height=TEXT_BOX_HEIGHT, font=FONT)
        t.pack(
            fill='x',
            padx=constants.PAD,
            pady=(constants.QUARTER, 2 * constants.QUARTER),
        )
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


def _set_entry_text(entry: CTkEntry, text: str) -> None:
    entry.delete(0, 'end')
    entry.insert(0, text)
