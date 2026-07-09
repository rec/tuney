from tuney import cli
from tuney.cfg.tuney import Tuney


def main() -> None:
    cli.cli(Tuney, 'tuney')


if __name__ == '__main__':
    main()
