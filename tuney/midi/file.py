from __future__ import annotations

from pathlib import Path

import mido

from ..audio.mixer import NotePress
from .midi import ZERO_IS_NOTE_OFF, MidiOut

MIDI_FILE_SUFFIXES = {'.mid', '.midi', '.smf'}
MIDI_FILE_TEMPO = 1_000_000
MIDI_FILE_TICKS_PER_BEAT = 1000


def is_midi_file(path: Path) -> bool:
    return path.suffix.lower() in MIDI_FILE_SUFFIXES


def write_midi_file(
    path: Path, events: list[tuple[int, NotePress]], midi: MidiOut
) -> None:
    file = mido.MidiFile(ticks_per_beat=MIDI_FILE_TICKS_PER_BEAT)
    track = mido.MidiTrack()
    file.tracks.append(track)
    track.append(mido.MetaMessage('set_tempo', tempo=MIDI_FILE_TEMPO, time=0))
    track.append(midi.send_program_change(0))
    track.append(midi.send_volume_change(0))
    previous = 0
    for frame, note in events:
        tick = max(0, round(frame))
        track.append(_midi_file_message(midi, note, tick - previous))
        previous = tick
    file.save(str(path))


def _midi_file_message(midi: MidiOut, note: NotePress, time: int) -> mido.Message:
    kwargs = {} if midi.mido_channel is None else {'channel': midi.mido_channel}
    return mido.Message(
        **kwargs,
        note=midi.midi_note(note.note_number),
        time=time,
        type='note_on' if note.is_press or ZERO_IS_NOTE_OFF else 'note_off',
        velocity=max(0, min(127, note.is_press * midi.velocity)),
    )
