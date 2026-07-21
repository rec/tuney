from textual.app import App, ComposeResult
from textual.widgets import Static

CSS = """Screen {
    layout: grid;
    grid-size: 1;
    background: white;
}"""


class Grid(App):
    theme = 'textual-light'
    CSS = CSS

    def __init__(self, *a: object, **ka: object) -> None:
        super().__init__(*a, **ka)
        # self.resize_grid()  # Cannot be called here

    def compose(self) -> ComposeResult:
        self.resize_grid()
        for i in range(9):
            yield Static(str(i))
        # self.resize_grid()

    def resize_grid(self) -> None:
        # From https://textual.textualize.io/styles/grid/grid_size/#python
        # Does nothing
        for s in (self.screen.styles,):
            s.grid_size_columns = 3
            s.grid_size_rows = 3


if __name__ == '__main__':
    Grid().run()
