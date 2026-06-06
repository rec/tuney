from . import cli
from .ui.app import App


def main() -> None:
    cli.cli(App, 'tuney')


if __name__ == '__main__':
    main()
