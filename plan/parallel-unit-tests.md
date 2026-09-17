# Parallel unit tests

## Goal

Run tuney's unit suite concurrently in developer and release workflows without
changing what the tests cover or allowing tests to touch shared user state,
hardware, or regression fixtures concurrently.

The target command is:

```sh
QT_QPA_PLATFORM=offscreen uv run pytest -n auto --dist=loadfile
```

`pytest-xdist` starts one worker process per physical CPU for `-n auto`.
`--dist=loadfile` keeps every test in one module on the same worker. That
preserves module-local Qt state and test ordering assumptions while still
spreading the 40-plus test modules across workers. Developers can choose a
smaller fixed worker count with `-n 2`, or diagnose a failure serially with
`-n 0`.

Do not make `-n auto` a global pytest `addopts` setting. Focused local runs and
debugging should retain pytest's ordinary single-process behavior unless the
caller explicitly selects parallel execution.

## Current state

- `pytest-xdist` is not a development dependency, so pytest currently has no
  `-n` option.
- The suite already has useful isolation: filesystem tests use `tmp_path`,
  persistence tests replace XDG roots or application paths, and tests which
  require a fresh Qt application run through `test/_test_app_keys.py` in their
  own subprocesses.
- Qt widgets also appear in ordinary test modules. A shared, headless Qt
  platform setting must be established before any PySide6 import so workers and
  subprocesses behave the same in CI and on desktop development machines.
- `file_regression` fixtures are committed expected files. Normal tests compare
  them safely in parallel; fixture regeneration must remain a deliberate,
  serial review operation.
- Export-job tests create their own multiprocessing children. xdist workers are
  also processes, so the implementation must be tested with both nesting levels.

## Implementation

1. Add `pytest-xdist` to the `dev` dependency group in `pyproject.toml`, update
   `uv.lock`, and retain it only as a development dependency.

2. Update the root `conftest.py` to set `QT_QPA_PLATFORM=offscreen` with
   `os.environ.setdefault` before test modules import PySide6. Retain the
   existing Reccy pytest-plugin declaration. Keep an explicitly supplied
   platform value unchanged, so native GUI troubleshooting remains possible.

3. Audit and fix any failures from an initial `-n auto --dist=loadfile` trial.
   The fixes must make ownership explicit rather than serializing broad groups:

   - Give every test that reaches user configuration, autosave, presets, logs,
     crash markers, or instance claims a worker-local temporary root.
   - Preserve `tmp_path` for temporary audio, export, and regression inputs.
   - Keep real audio devices, MIDI devices, keyboard listeners, and speech
     engines mocked or disabled. No worker may claim a real device.
   - Keep the existing child-process timeout for Qt checks and add worker-safe
     cleanup for any module globals it exposes.
   - Keep `--force-regen` out of parallel commands. Regenerate and review
     snapshots serially with `-n 0`.

4. Add a documented developer command to `README.md` and
   `doc/maintaining-tuney.md`:

   ```sh
   QT_QPA_PLATFORM=offscreen uv run pytest -n auto --dist=loadfile
   ```

   Document `-n 0` as the reproduction command and `-n N` as the bounded local
   alternative. Do not add a shell wrapper unless repeated workflow commands
   show that one is needed.

5. Change the release workflow's test step to the same explicit command. Keep
   the existing `UV_NO_SOURCES=1` setting, so parallel tests continue to verify
   the pinned release dependencies rather than editable siblings.

6. Add a small CI test matrix only if the first implementation exposes a
   platform-specific race: one serial Linux job for the clearest failures and
   parallel release-platform jobs for packaging confidence. Otherwise, retain
   the current release matrix and make its one test step parallel.

## Validation and acceptance criteria

1. Run the full suite serially with `-n 0`, then run it with `-n auto
   --dist=loadfile` three times from a clean worktree. All runs must have the
   same passing test count and leave no files outside pytest temporary roots.

2. Run the parallel suite once with `UV_NO_SOURCES=1` in a fresh exported
   checkout. This verifies that worker processes also use the pinned release
   dependencies.

3. Run the existing Python checks after the change:

   ```sh
   uv run ruff check --fix --select B,E,F,I tuney test
   uv run ruff format tuney test
   uv run ty check tuney
   find test tuney -name '*.py' -print0 | xargs -0 uv run pyupgrade --py313-plus
   git diff --check
   ```

4. Inspect xdist's failure output for complete node IDs and worker tracebacks.
   A failure must reproduce with `-n 0` or be treated as a test-isolation defect;
   do not paper over it with reruns or a broad serial marker.

5. Record serial and parallel elapsed times on the development machine and one
   GitHub Actions platform. Keep the change only if the parallel command gives a
   material improvement without flakiness or excessive memory use. If `-n auto`
   oversubscribes a machine, document a fixed `-n N` recommendation based on the
   measurement rather than guessing a global cap.

## Non-goals

- Running real audio, MIDI, keyboard, speech, or desktop-window integration
  tests concurrently.
- Parallel snapshot regeneration.
- Changing test semantics, deleting timeouts, or weakening the existing
  subprocess isolation for Qt tests.
- Adding CI sharding or remote test distribution before local worker parallelism
  is stable.
