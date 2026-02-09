from collections.abc import Sequence
from functools import cached_property
from typing import Any

from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.widgets import Static

from tuney.ui import ColumnsRows, Text

FLAT = ('C', 'D♭', 'D', 'E♭', 'E', 'F', 'G♭', 'G', 'A♭', 'A', 'B♭', 'B')


class NoteGrid(App):
    theme = 'textual-light'
    CSS_PATH = 'note_grid.tcss'

    version = reactive(0, recompose=True)

    texts: Sequence[Text]

    def __init__(self, texts: Sequence[Text], *args: Any, **kwargs: Any) -> None:
        self.texts = texts
        super().__init__(*args, **kwargs)

    def redraw(self) -> None:
        self.version += 1

    def compose(self) -> ComposeResult:
        self.resize_grid()
        for t in self.texts:
            yield Static('\n'.join(t.labels), classes='on' if t.on else 'off')

    @cached_property
    def shape(self) -> ColumnsRows:
        return ColumnsRows.from_length(len(self.texts))

    def resize_grid(self) -> None:
        # From https://textual.textualize.io/styles/grid/grid_size/#python
        self.screen.styles.grid_size_columns = self.shape[0]
        self.screen.styles.grid_size_rows = self.shape[1]

    def stop(self) -> Any:
        return self.exit()


def _text(i: int) -> Text:
    s = FLAT[i % len(FLAT)]
    return Text((s, s), len(s) > 1)


TEXTS = [_text(i) for i in range(len(FLAT))]


if __name__ == '__main__':
    import sys

    count = int(sys.argv[1])
    NoteGrid([_text(i) for i in range(count)]).run()
