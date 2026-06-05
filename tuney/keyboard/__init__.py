from pynput.keyboard import Key, KeyCode

type KeyType = Key | KeyCode

WHITESPACE = {Key.space: ' ', Key.enter: '\n', Key.backspace: '\b'}
