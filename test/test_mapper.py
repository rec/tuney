from string import ascii_lowercase, ascii_uppercase

from tuney.audio.sound import Sound
from tuney.mapper.language import alphabet_for_language_name
from tuney.mapper.mapper import Mapper


def _final_note_numbers(mapper: Mapper) -> list[int]:
    note_offset = Sound().note_offset
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


def test_language_alphabet_can_be_used_as_mapper_alphabet() -> None:
    mapper = Mapper(alphabet=alphabet_for_language_name('French', True))

    assert mapper.alphabet is not None
    assert mapper.alphabet.startswith('ABCDEFGHIJKLMNOPQRSTUVWXYZÀÂ')
    assert 'É' in mapper.alphabet
    assert 'ç' in mapper.alphabet


def test_mapper_uses_default_alphabet() -> None:
    assert Mapper().alphabet == ascii_uppercase + ascii_lowercase


def test_language_alphabet_respects_case_sensitive() -> None:
    mapper = Mapper(
        alphabet=alphabet_for_language_name('Turkish', False),
        case_sensitive=False,
    )

    assert mapper.alphabet_ == 'abcçdefgğhıijklmnoöprsştuüvyz'


def test_mapper_regenerates_default_alphabet_when_case_sensitivity_changes() -> None:
    data = Mapper().model_dump()
    data['case_sensitive'] = False

    mapper = Mapper.model_validate(data)

    assert mapper.alphabet == ascii_lowercase
    assert mapper('a') == Mapper(case_sensitive=False)('a')


def test_mapper_wraps_notes_outside_range_limit() -> None:
    mapper = Mapper(alphabet=''.join(chr(i) for i in range(70)))
    values = list(mapper.char_to_number.values())

    assert min(values) == -10
    assert max(values) == 49
    assert values[:6] == [45, 46, 47, 48, 49, -10]
    assert values[-6:] == [49, -10, -9, -8, -7, -6]


def test_mapper_reflects_notes_outside_range_limit() -> None:
    mapper = Mapper(
        alphabet=''.join(chr(i) for i in range(70)),
        limiter='reflect',
    )
    values = list(mapper.char_to_number.values())

    assert min(values) == -10
    assert max(values) == 49
    assert values[:6] == [-5, -6, -7, -8, -9, -10]
    assert values[-6:] == [49, 48, 47, 46, 45, 44]


def test_mapper_reflects_notes_with_repeated_turnaround() -> None:
    mapper = Mapper(
        alphabet=''.join(chr(i) for i in range(70)),
        limiter='reflect_repeat',
    )
    values = list(mapper.char_to_number.values())

    assert min(values) == -10
    assert max(values) == 49
    assert values[:6] == [-6, -7, -8, -9, -10, -10]
    assert values[-6:] == [49, 49, 48, 47, 46, 45]
