from .ui.controller import KeyboardController


def main() -> None:
    with KeyboardController():
        pass


if __name__ == "__main__":
    main()
