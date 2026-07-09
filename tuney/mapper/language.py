from __future__ import annotations

from pydantic import BaseModel


def alphabet_for_language(language: str | None, case_sensitive: bool) -> str | None:
    if (tag := _language_tag(language)) is None:
        return None
    if (alphabet := ALPHABETS.get(tag)) is None:
        alphabet = ALPHABETS.get(tag.split('-', 1)[0])
    if alphabet is None:
        return None
    return alphabet.both if case_sensitive else alphabet.lower


def known_language(language: str) -> bool:
    if (tag := _normalized_language_tag(language)) is None:
        return False
    return tag in ALPHABETS or tag.split('-', 1)[0] in ALPHABETS


def _language_tag(language: str | None) -> str | None:
    if not language:
        return None
    return _normalized_language_tag(language)


def _normalized_language_tag(language: str) -> str | None:
    tag = language.split('.', 1)[0].split('@', 1)[0].replace('_', '-').casefold()
    if tag in {'c', 'posix'}:
        return None
    return tag


class Alphabet(BaseModel, frozen=True):
    upper: str
    lower: str

    @property
    def both(self) -> str:
        return self.upper + self.lower


def _alphabet(upper: str, lower: str | None = None) -> Alphabet:
    return Alphabet(upper=upper, lower=lower or upper.lower())


ALPHABETS = {
    'cs': _alphabet('AÁBCČDĎEÉĚFGHCHIÍJKLMNŇOÓPQRŘSŠTŤUÚŮVWXYÝZŽ'),
    'da': _alphabet('ABCDEFGHIJKLMNOPQRSTUVWXYZÆØÅ'),
    'de': _alphabet('ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜẞ', 'abcdefghijklmnopqrstuvwxyzäöüß'),
    'el': _alphabet('ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ', 'αβγδεζηθικλμνξοπρστυφχψω'),
    'en': _alphabet('ABCDEFGHIJKLMNOPQRSTUVWXYZ'),
    'es': _alphabet('ABCDEFGHIJKLMNÑOPQRSTUVWXYZ'),
    'fi': _alphabet('ABCDEFGHIJKLMNOPQRSTUVWXYZÅÄÖ'),
    'fr': _alphabet(
        'ABCDEFGHIJKLMNOPQRSTUVWXYZÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸ',
        'abcdefghijklmnopqrstuvwxyzàâæçéèêëîïôœùûüÿ',
    ),
    'hu': _alphabet('AÁBCDEÉFGHIÍJKLMNOÓÖŐPQRSTUÚÜŰVWXYZ'),
    'is': _alphabet('AÁBDÐEÉFGHIÍJKLMNOÓPRSTUÚVXYÝÞÆÖ'),
    'it': _alphabet('ABCDEFGHIJKLMNOPQRSTUVWXYZ'),
    'nl': _alphabet('ABCDEFGHIJKLMNOPQRSTUVWXYZ'),
    'no': _alphabet('ABCDEFGHIJKLMNOPQRSTUVWXYZÆØÅ'),
    'pl': _alphabet('AĄBCĆDEĘFGHIJKLŁMNŃOÓPRSŚTUWYZŹŻ'),
    'pt': _alphabet('ABCDEFGHIJKLMNOPQRSTUVWXYZÇ'),
    'ro': _alphabet('AĂÂBCDEFGHIÎJKLMNOPQRSȘTȚUVWXYZ'),
    'ru': _alphabet('АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'),
    'sk': _alphabet('AÁÄBCČDĎDZEÉFGHCHIÍJKLMNŇOÓÔPQRŔSŠTŤUÚVWXYÝZŽ'),
    'sv': _alphabet('ABCDEFGHIJKLMNOPQRSTUVWXYZÅÄÖ'),
    'tr': _alphabet('ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ', 'abcçdefgğhıijklmnoöprsştuüvyz'),
}
