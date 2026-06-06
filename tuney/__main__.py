from . import cli
from .ui.tuney import Tuney


def main() -> None:
    cli.cli(Tuney, 'tuney')


if __name__ == '__main__':
    main()
