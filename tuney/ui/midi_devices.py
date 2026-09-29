from __future__ import annotations

from queue import Empty, Full
from threading import Event
from typing import TYPE_CHECKING

from PySide6 import QtWidgets

from ..app.platform_info import report_error
from ..midi.ports import midi_names, probe_midi_names

if TYPE_CHECKING:
    from .main_window import MainWindow

MIDI_DEVICE_POLL_IN_SECONDS = 2


def watch_midi_devices(window: MainWindow, stop_event: Event) -> None:
    names = midi_names()
    names = [
        new if new is not None else old
        for new, old in zip(probe_midi_names(), names, strict=True)
    ]
    if stop_event.is_set():
        return
    midi_names.replace(names)
    while not stop_event.wait(MIDI_DEVICE_POLL_IN_SECONDS):
        updated = [
            new if new is not None else old
            for new, old in zip(probe_midi_names(), names, strict=True)
        ]
        if stop_event.is_set():
            return
        if updated != names:
            names = updated
            midi_names.replace(updated)
            try:
                window.midi_device_queue.put_nowait(updated)
            except Full:
                try:
                    window.midi_device_queue.get_nowait()
                except Empty:
                    pass
                window.midi_device_queue.put_nowait(updated)


def on_midi_devices_changed(window: MainWindow, names: list[list[str]]) -> None:
    output_name = window.app.midi.output.name
    window.ui.refresh_midi_devices()
    input = window.app.midi.input
    if (
        input.enable
        and window.app.midi_listener.port is None
        and (input.name is None or input.name in names[0])
    ):
        window.app.midi_listener.start()
    if output_name and output_name not in names[1]:
        window.app.midi.output.close()
        window.app.midi.output.name = None
        window.ui.refresh_midi_devices()
        QtWidgets.QMessageBox.information(
            window,
            'MIDI output device missing',
            f'Output device {output_name} no longer exists',
        )
        try:
            window.app._autosave.save(window.app.save_autosave)
        except (OSError, ValueError) as error:
            report_error(
                f'Could not save autosave after MIDI output disappeared: {error}'
            )


def on_midi_output_failed(window: MainWindow, error: str) -> None:
    QtWidgets.QMessageBox.warning(
        window,
        'MIDI output failed',
        f'MIDI output failed: error {error}',
    )
    window.ui.rebuild_control_panel()
    try:
        window.app._autosave.save(window.app.save_autosave)
    except (OSError, ValueError) as save_error:
        report_error(f'Could not save autosave after MIDI output failure: {save_error}')
