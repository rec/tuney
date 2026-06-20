from tuney.audio.multi_player import MultiPlayer
from tuney.mapper.mapper import Mapper


def _final_note_numbers(mapper: Mapper) -> list[int]:
    note_offset = MultiPlayer().note_offset
    return [note_number + note_offset for note_number in mapper.char_to_number.values()]


def test_mapper_default_notes_center_between_63_and_64() -> None:
    note_numbers = _final_note_numbers(Mapper())

    assert min(note_numbers) == 38
    assert max(note_numbers) == 89
    assert min(note_numbers) + max(note_numbers) == 127


def test_mapper_offset_moves_center() -> None:
    note_numbers = _final_note_numbers(Mapper(offset=12))

    assert min(note_numbers) == 50
    assert max(note_numbers) == 101
    assert min(note_numbers) + max(note_numbers) == 151


def test_mapper_length_is_centered() -> None:
    mapper = Mapper(alphabet='abcdef', length=3)

    assert [mapper(char) for char in 'abcdef'] == [19, 20, 21, 19, 20, 21]
