from __future__ import annotations

import sys

from . import platform_info
from .app_playback import AppPlayback


class App(AppPlayback):
    """Turn text into music.

    Use positional `TEXT` to play characters as notes, then tune the scale,
    audio, MIDI, and timing from the same config model.
    """

    def run(self) -> None:
        platform_info.instrument(
            'run', gui=self.gui, frozen=getattr(sys, 'frozen', False)
        )
        if self.gui:
            platform_info.start_crash_logging()
            if not platform_info.acquire_single_instance():
                platform_info.show_already_running()
                return
            try:
                crashed = platform_info.mark_session_started()
                restore_error = None
                try:
                    platform_info.instrument('autosave restore start')
                    restore_error = self._autosave.restore(self)
                    platform_info.instrument(
                        'autosave restore end', error=restore_error is not None
                    )
                except Exception as error:
                    platform_info.instrument(
                        'autosave restore exception', error=repr(error)
                    )
                    restore_error = error
                platform_info.instrument('main window construct start')
                main_window = self.main_window
                platform_info.instrument('main window construct end')
                if crashed:
                    main_window.show_crash_report()
                if restore_error is not None:
                    main_window.show_restore_error(restore_error)
                self.start()
                platform_info.instrument('mainloop start')
                main_window.mainloop()
                platform_info.mark_session_clean_exit()
                platform_info.instrument('mainloop end')
            finally:
                platform_info.release_single_instance()
        else:
            self.run_cli()

    def start(self) -> None:
        platform_info.instrument('app start', run_in_background=self.run_in_background)
        self.main_window.start()
        self.midi_listener.start()
        self.midi.output.start()
        self.midi.output.send_tuning_dump(self.scale, self.tuning)
        if error := self.midi.output.pop_open_error():
            self.main_window.on_midi_output_failed(error)
        self.main_window.sync_midi_device_monitor()
        if self.run_in_background:
            self.keyboard_listener.start()
