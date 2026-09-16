from __future__ import annotations

import tempfile
from multiprocessing import get_context
from multiprocessing.connection import Connection
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from pydantic import BaseModel

from ..audio.test_sheet import prepare_test_sheet, render_test_sheet
from .app import App


class ExportRequest(BaseModel, frozen=True):
    output: Path
    scratch: Path
    settings: dict[str, object]
    presets: list[dict[str, object]] | None = None


class ExportUpdate(BaseModel, frozen=True):
    percent: int = 0
    message: str = 'Preparing export'
    success: bool = False
    error: str | None = None


class ExportJob:
    """The parent alone publishes output; a disposable process renders it."""

    def __init__(
        self, destination: Path, app: App, preset_names: list[str] | None = None
    ) -> None:
        settings = _snapshot(app)
        presets = (
            None
            if preset_names is None
            else [_snapshot(p) for p in prepare_test_sheet(app, preset_names)]
        )
        with NamedTemporaryFile(
            prefix=f'.{destination.stem}-',
            suffix=destination.suffix,
            dir=destination.parent,
            delete=False,
        ) as file:
            self.temporary = Path(file.name)
        self.destination = destination
        self.scratch = TemporaryDirectory(prefix='tuney-export-')
        self.cancelled = False
        self.finished = False
        self.update = ExportUpdate()
        context = get_context('spawn')
        self.receiver, sender = context.Pipe(duplex=False)
        self.process = context.Process(
            target=render_export,
            args=(
                ExportRequest(
                    output=self.temporary,
                    scratch=Path(self.scratch.name),
                    settings=settings,
                    presets=presets,
                ),
                sender,
            ),
            daemon=True,
        )
        try:
            self.process.start()
        except (OSError, RuntimeError, ValueError):
            self.receiver.close()
            self.process.close()
            self.temporary.unlink(missing_ok=True)
            self.scratch.cleanup()
            raise
        finally:
            sender.close()

    def cancel(self) -> None:
        if not self.finished:
            self.cancelled = True
            if self.process.is_alive():
                self.process.terminate()

    def poll(self) -> bool:
        if self.finished:
            return True
        self._read_updates()
        if self.process.is_alive():
            return False
        self.process.join()
        self._read_updates()
        try:
            if not self.cancelled:
                if self.process.exitcode != 0 or not self.update.success:
                    self.update = self.update.model_copy(
                        update={
                            'error': self.update.error
                            or f'Export worker failed (exit {self.process.exitcode})'
                        }
                    )
                else:
                    self.temporary.replace(self.destination)
        except OSError as error:
            self.update = self.update.model_copy(update={'error': str(error)})
        finally:
            try:
                self.temporary.unlink(missing_ok=True)
                self.scratch.cleanup()
            except OSError as error:
                self.update = self.update.model_copy(update={'error': str(error)})
            finally:
                self.receiver.close()
                self.process.close()
                self.finished = True
        return True

    def close(self) -> None:
        if not self.finished:
            self.cancel()
            self.process.join()
            self.poll()

    def _read_updates(self) -> None:
        while self.receiver.poll():
            try:
                self.update = self.receiver.recv()
            except EOFError:
                break


def render_export(request: ExportRequest, sender: Connection) -> None:
    # This process is isolated. The parent owns speech scratch files too, so
    # terminating a native speech engine does not leave its WAV files behind.
    tempfile.tempdir = str(request.scratch)
    previous: ExportUpdate | None = None

    def progress(fraction: float, message: str) -> None:
        nonlocal previous
        update = ExportUpdate(percent=min(99, int(fraction * 100)), message=message)
        if update != previous:
            sender.send(update)
            previous = update

    try:
        app = App.model_validate(request.settings)
        if request.presets is None:
            progress(0, 'Preparing speech' if app.use_speech else 'Preparing audio')
            speech = app.render_output_speech()
            app.player.render_file(
                request.output,
                app.note_events(app.player.sample_rate),
                app.output_comment(),
                speech,
                lambda frames, total: progress(
                    frames / max(1, total), 'Rendering audio'
                ),
            )
        else:
            render_test_sheet(
                request.output,
                app,
                [App.model_validate(p) for p in request.presets],
                progress,
            )
        sender.send(ExportUpdate(percent=100, message='Export complete', success=True))
    except (OSError, RuntimeError, ValueError, ArithmeticError, TypeError) as error:
        sender.send(ExportUpdate(error=str(error)))
    finally:
        sender.close()


def _snapshot(app: App) -> dict[str, object]:
    return app.dump_data() | {'gui': False, 'text_file': None, 'text_args': []}
