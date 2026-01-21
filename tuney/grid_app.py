import dataclasses as dc

from textual.app import App, ComposeResult
from textual.widgets import Static
from textual.color import Color
from typing import Sequence

RED, GREY = Color.parse("orange"), Color.parse("grey")

FLAT = ("C", "D♭", "D", "E♭", "E", "F", "G♭", "G", "A♭", "A", "B♭", "B")


@dc.dataclass
class Text:
    labels: Sequence[str]
    on: bool = False



class NoteGrid(App):
    theme = "textual-light"
    grid_items: Sequence[Text]

    def compose(self) -> ComposeResult:
        for t in self.text_items:
            yield Static("\n".join(t.labels), classes="on" if t.on else "off")


def to_columns_rows(n: int) -> tuple[int, int]:
    rows = int(n**0.5)
    columns = n // rows
    return columns + ((rows * columns) < n), rows


def make_app(items: Sequence[str]) -> App:
    columns, rows = to_columns_rows(len(items))

    g = NoteGrid()
    css = CSS.format(columns=columns, rows=rows)
    g.__dict__.update(text_items=items, CSS=css)
    return g


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
}}"""


if __name__ == "__main__":
    import sys

    def text(i: int) -> Text:
        s = FLAT[i % len(FLAT)]
        return Text((s, s), len(s) > 1)

    count = int(sys.argv[1])
    app = make_app([text(i) for i in range(count)])
    app.run()
