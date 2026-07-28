from __future__ import annotations

import sys

from . import platform_info as pi
from .app_playback import AppPlayback


class App(AppPlayback):
    """Turn text into music.

    Use positional `TEXT` to play characters as notes, then tune the scale,
    audio, MIDI, and timing from the same config model.
    """

    def run(self) -> None:
        pi.instrument('run', gui=self.gui, frozen=getattr(sys, 'frozen', False))
        if self.gui:
            pi.start_crash_logging()
            if not pi.acquire_single_instance():
                pi.show_already_running()
                return
            try:
                crashed = pi.mark_session_started()
                restore_error = None
                try:
                    pi.instrument('autosave restore start')
                    restore_error = self._autosave.restore(self)
                    pi.instrument(
                        'autosave restore end', error=restore_error is not None
                    )
                except Exception as error:
                    pi.instrument('autosave restore exception', error=repr(error))
                    restore_error = error
                pi.instrument('main window construct start')
                main_window = self.main_window
                pi.instrument('main window construct end')
                if crashed:
                    main_window.show_crash_report()
                if restore_error is not None:
                    main_window.show_restore_error(restore_error)
                self.start()
                pi.instrument('mainloop start')
                main_window.mainloop()
                pi.mark_session_clean_exit()
                pi.instrument('mainloop end')
            finally:
                pi.release_single_instance()
        else:
            self.run_cli()

    def start(self) -> None:
        pi.instrument('app start', run_in_background=self.run_in_background)
        self.main_window.start()
        self.midi_listener.start()
        self.midi.output.start()
        self.midi.output.send_tuning_dump(self.scale, self.tuning)
        if error := self.midi.output.pop_open_error():
            self.main_window.on_midi_output_failed(error)
        if self.run_in_background:
            self.keyboard_listener.start()
