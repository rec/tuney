from textual.app import App, ComposeResult
from textual.widgets import Static
from textual.color import Color
from typing import Sequence

RED, GREY = Color.parse("orange"), Color.parse("grey")

FLAT = ("C", "D♭", "D", "E♭", "E", "F", "G♭", "G", "A♭", "A", "B♭", "B")

CSS = """
Screen {{
    layout: grid;
    grid-size: {columns} {rows};
    background: white;
}}
Static {{
    height: 100%;
    content-align-horizontal: center;
    content-align-vertical: middle;
}}
.on {{
    border: solid green;
    color: orange;
    text-style: bold;
}}
.off {{
    border: lightblue;
    color: lightgrey;
}}
"""


class NoteGridBase(App):
    theme = 'textual-light'
    text_items: Sequence[str]

    def compose(self) -> ComposeResult:
        for t in self.text_items:
            yield Static(t, classes="on" if t == "C" else "off")


def to_columns_rows(n: int) -> tuple[int, int]:
    rows = int(n ** 0.5)
    columns = n // rows
    return columns + ((rows * columns) < n), rows


def make_app(items: Sequence[str]) -> App:
    columns, rows = to_columns_rows(len(items))

    class NoteGrid(NoteGridBase):
        CSS = CSS.format(columns=columns, rows=rows)
        text_items = items

    return NoteGrid()


if __name__ == "__main__":
    import sys

    app = make_app((FLAT * 100)[:int(sys.argv[1])])
    app.run()
