from threading import Thread, get_ident

import mido

from tuney.midi.listener import MidiListener
from tuney.midi.midi import Midi, MidiIn


def test_midi_messages_play_in_order_on_the_consuming_thread() -> None:
    played: list[tuple[int, bool, int]] = []
    midi = Midi(input=MidiIn(channel=2))
    listener = MidiListener(
        midi, lambda note, pressed: played.append((note, pressed, get_ident()))
    )

    def receive() -> None:
        listener.on_message(mido.Message('note_on', note=60, channel=1))
        listener.on_message(mido.Message('note_on', note=60, channel=1, velocity=0))
        listener.on_message(mido.Message('note_on', note=61, channel=0))
        listener.on_message(mido.Message('control_change', channel=1))
        listener.on_message(mido.Message('note_off', note=62, channel=1))

    thread = Thread(target=receive)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert played == []
    listener.dispatch_pending()
    assert played == [
        (midi.output.tuney_note(60), True, get_ident()),
        (midi.output.tuney_note(60), False, get_ident()),
        (midi.output.tuney_note(62), False, get_ident()),
    ]
    listener.dispatch_pending()
    assert len(played) == 3


def test_closing_midi_input_discards_pending_messages() -> None:
    played: list[int] = []
    listener = MidiListener(Midi(), lambda note, pressed: played.append(note))
    listener.on_message(mido.Message('note_on', note=60))
    listener.close()
    listener.dispatch_pending()
    assert played == []
