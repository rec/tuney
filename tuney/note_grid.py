import dataclasses as dc
import math
from typing import Any, Iterable, Sequence

from textual.app import App, ComposeResult
from textual.widgets import Static

FLAT = ("C", "D♭", "D", "E♭", "E", "F", "G♭", "G", "A♭", "A", "B♭", "B")


@dc.dataclass
class Text:
    labels: Sequence[str]
    on: bool = False


class NoteGrid(App):
    theme = "textual-light"
    texts: Iterable[Text]

    def __init__(self, texts: Iterable[Text], *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.texts = texts
        css = CSS.format(columns=int(math.ceil(len(texts) ** 0.5)))
        self.CSS = css  # ty: ignore[invalid-attribute-access]

    def compose(self) -> ComposeResult:
        for t in self.texts:
            yield Static("\n".join(t.labels), classes="on" if t.on else "off")


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


if __name__ == "__main__":
    import sys

    def text(i: int) -> Text:
        s = FLAT[i % len(FLAT)]
        return Text((s, s), len(s) > 1)

    count = int(sys.argv[1])
    NoteGrid([text(i) for i in range(count)]).run()
