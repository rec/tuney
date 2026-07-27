from __future__ import annotations

from math import floor, log2

import mido

from ..scale.scale import Scale
from ..scale.tuning import Tuning

MTS_DEVICE_ID_ALL = 0x7F
MTS_SUB_ID = 0x08
MTS_BULK_DUMP = 0x01
MTS_TUNING_PROGRAM = 0
MTS_TUNING_NAME = 'Tuney'
MTS_NO_CHANGE = [0x7F, 0x7F, 0x7F]
MIDI_A4 = 69
A4_FREQUENCY = 440.0
SEMITONE_FRACTIONS = 16_384


def tuning_dump(scale: Scale, tuning: Tuning, note_offset: int = 0) -> mido.Message:
    name = _ascii_bytes(MTS_TUNING_NAME, 16)
    frequencies = [
        b
        for note in range(128)
        for b in _frequency_bytes(scale.frequency(tuning, (note - note_offset) % 128))
    ]
    data = [
        0x7E,
        MTS_DEVICE_ID_ALL,
        MTS_SUB_ID,
        MTS_BULK_DUMP,
        MTS_TUNING_PROGRAM,
        *name,
        *frequencies,
    ]
    data.append(_tuning_checksum(data))
    return mido.Message('sysex', data=data)


def _ascii_bytes(text: str, length: int) -> list[int]:
    data = [ord(c) if 32 <= ord(c) <= 127 else ord(' ') for c in text[:length]]
    return data + [ord(' ')] * (length - len(data))


def _frequency_bytes(frequency: float) -> list[int]:
    if frequency <= 0:
        return list(MTS_NO_CHANGE)
    note = MIDI_A4 + 12 * log2(frequency / A4_FREQUENCY)
    semitone = floor(note)
    fraction = round((note - semitone) * SEMITONE_FRACTIONS)
    if fraction == SEMITONE_FRACTIONS:
        semitone += 1
        fraction = 0
    if not 0 <= semitone <= 127:
        return list(MTS_NO_CHANGE)
    return [semitone, fraction >> 7, fraction & 0x7F]


def _tuning_checksum(data: list[int]) -> int:
    checksum = 0
    for b in [data[0], data[1], *data[3:]]:
        checksum ^= b
    return checksum
