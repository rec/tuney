from . import cli
from .tuney import Tuney


def main() -> None:
    cli.cli(Tuney, 'tuney')


if __name__ == '__main__':
    main()
