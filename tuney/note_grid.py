import dataclasses as dc
import math
from collections.abc import Collection, Sequence
from typing import Any, Iterable

from textual.app import App, ComposeResult
from textual.widgets import Static

FLAT = ("C", "D♭", "D", "E♭", "E", "F", "G♭", "G", "A♭", "A", "B♭", "B")


@dc.dataclass
class Text:
    labels: Sequence[str]
    on: bool = False


class NoteGrid(App):
    theme = "textual-light"
    texts: Collection[Text]

    def __init__(self, texts: Collection[Text], *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.texts = texts
        cols = int(math.ceil(len(self.texts) ** 0.5))
        if True:
            self.CSS = CSS.format(columns=cols)  # ty: ignore[invalid-attribute-access]
        else:
            self.styles.grid_size_columns = cols  # Does nothing.

    def compose(self) -> ComposeResult:
        for t in self.texts:
            yield Static("\n".join(t.labels), classes="on" if t.on else "off")

    def stop(self) -> Any:
        return self.exit()


CSS = """
Screen {{
    layout: grid;
    grid-size: {columns};
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
    border: solid lightblue;
    color: lightgrey;
}}"""


def _text(i: int) -> Text:
    s = FLAT[i % len(FLAT)]
    return Text((s, s), len(s) > 1)


TEXTS = [_text(i) for i in range(len(FLAT))]


if __name__ == "__main__":
    import sys

    count = int(sys.argv[1])
    NoteGrid([_text(i) for i in range(count)]).run()
