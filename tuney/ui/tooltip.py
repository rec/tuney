from collections.abc import Callable
from tkinter import Event, Label, Misc, Toplevel


class Tooltip:
    def __init__(
        self,
        widget: Misc,
        text: str,
        hover_time: Callable[[], float],
    ) -> None:
        self.widget = widget
        self.text = text
        self.hover_time = hover_time
        self.after_id: str | None = None
        self.window: Toplevel | None = None
        widget.bind('<Enter>', self._schedule, add='+')
        widget.bind('<Leave>', self._hide, add='+')
        widget.bind('<ButtonPress>', self._hide, add='+')

    def _schedule(self, _: Event) -> None:
        self._cancel()
        self.after_id = self.widget.after(round(self.hover_time() * 1000), self._show)

    def _cancel(self) -> None:
        if self.after_id is not None:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def _show(self) -> None:
        self.after_id = None
        self.window = Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_attributes('-topmost', True)
        self.window.wm_geometry(
            f'+{self.widget.winfo_rootx()}+'
            f'{self.widget.winfo_rooty() + self.widget.winfo_height() + 4}'
        )
        Label(
            self.window,
            text=self.text,
            background='#ffffe0',
            foreground='black',
            borderwidth=1,
            relief='solid',
            justify='left',
            padx=6,
            pady=4,
            wraplength=320,
        ).pack()
        self.window.lift()

    def _hide(self, _: Event) -> None:
        self._cancel()
        if self.window is not None:
            self.window.destroy()
            self.window = None
