from __future__ import annotations

from ..time.char_press import CharPress


def edit_text_timing(
    char_presses: list[CharPress], row: int, column: int, text: str
) -> None:
    pairs = _text_timing_pairs(char_presses)
    if row < 0 or row >= len(pairs):
        return
    press_index, release_index = pairs[row]
    press = char_presses[press_index]
    if column == 0:
        char_presses[press_index] = press.model_copy(update={'char': text})
        if release_index is not None:
            release = char_presses[release_index]
            char_presses[release_index] = release.model_copy(update={'char': text})
    elif column == 1:
        delta = _validated_milliseconds(text)
        previous = char_presses[pairs[row - 1][0]].time if row else 0.0
        time_shift = previous + delta - press.time
        char_presses[press_index] = press.model_copy(
            update={'time': press.time + time_shift}
        )
        if release_index is not None:
            release = char_presses[release_index]
            char_presses[release_index] = release.model_copy(
                update={'time': release.time + time_shift}
            )
    elif column == 2:
        duration = None if not text.strip() else _validated_milliseconds(text)
        if duration is None and release_index is not None:
            char_presses.pop(release_index)
        elif duration is not None and release_index is None:
            char_presses.append(
                CharPress(press.char, False, time=press.time + duration)
            )
        elif duration is not None and release_index is not None:
            release = char_presses[release_index]
            char_presses[release_index] = release.model_copy(
                update={'time': press.time + duration}
            )
    char_presses.sort()


def text_timing_active_indexes(char_presses: list[CharPress]) -> dict[int, int | None]:
    result = {}
    pairs = _text_timing_pairs(char_presses)
    for row, (press_index, release_index) in enumerate(pairs):
        result[id(char_presses[press_index])] = row
        if release_index is not None:
            result[id(char_presses[release_index])] = None
    return result


def text_timing_rows(char_presses: list[CharPress]) -> list[list[str]]:
    rows = []
    pairs = _text_timing_pairs(char_presses)
    for i, (press_index, release_index) in enumerate(pairs):
        press = char_presses[press_index]
        previous = char_presses[pairs[i - 1][0]].time if i else 0.0
        duration = ''
        if release_index is not None:
            duration = f'{max(0.0, char_presses[release_index].time - press.time):g}'
        rows.append([press.char, f'{max(0.0, press.time - previous):g}', duration])
    return rows


def _text_timing_pairs(char_presses: list[CharPress]) -> list[tuple[int, int | None]]:
    rows: list[tuple[int, int | None]] = []
    active: dict[str, list[int]] = {}
    for i, c in enumerate(char_presses):
        if c.is_press:
            active.setdefault(c.char, []).append(len(rows))
            rows.append((i, None))
        elif indexes := active.get(c.char):
            row = indexes.pop()
            rows[row] = (rows[row][0], i)
    return rows


def _validated_milliseconds(text: str) -> float:
    return max(0.0, float(text))
