# Maintaining Tuney

This guide describes the boundaries that keep the desktop instrument and the
command-line renderer consistent.

## Architecture

`tuney.app.main:main` is the installed entry point. It parses an `App`, overlays
a preset or TOML/JSON configuration when requested, then starts GUI or CLI mode.
`--list-midi` is handled before normal application startup.

The mutable Pydantic application model is shared by every interface:

```text
App -> AppPlayback -> AppState -> AppMembers -> Tuney -> BaseModel
```

`Tuney` holds user-visible configuration. `AppMembers` owns cached runtime
collaborators. `AppState` validates edits, replaces configuration, persists
state, randomizes settings, and invalidates caches. `AppPlayback` converts
character events to audio and MIDI and implements offline rendering. `App`
owns the application lifecycle.

The GUI must update this one model through validation. Do not create a parallel
UI configuration model or freeze `App` or `Tuney`: GUI edits deliberately copy
validated values into the live mutable object.

| Area | Main package | Responsibility |
| --- | --- | --- |
| Application | `tuney/app/` | Lifecycle, state, playback, platform integration |
| Configuration | `tuney/config/` | Pydantic models, CLI metadata, serialization |
| Music | `tuney/mapper/`, `tuney/scale/` | Character mapping, scales, tunings, Scala data |
| Time | `tuney/time/` | Character presses, recording, sequencing |
| Audio | `tuney/audio/` | Voices, mixer, live output, offline rendering, speech |
| MIDI | `tuney/midi/` | Ports, input, output, files, tuning dumps |
| Input | `tuney/keyboard/` | Global keyboard listener and modifiers |
| Persistence | `tuney/presets/` | Presets and autosave |
| UI | `tuney/ui/` | Qt controls, transport, dialogs, note grid |

Tuney uses Ufor for shared musical definitions such as pitch arithmetic, tuning
definitions, Scala conversion, oscillator parameters, and gain. Tuney retains
its UI and CLI annotations, mutable application model, and expression handling.
Enge generates waveform buffers. Tuney's oscillator settings compose a Ufor
definition so library field names do not leak into its saved configuration.

For local development, keep the Reccy, Ufor, and Enge checkouts at `../reccy`,
`../ufor`, and `../enge`, then run `uv sync`. Release installations use the pinned
public source archives in `pyproject.toml`; Reccy and Enge are not currently
published on PyPI. Verify dependency updates in a separate checkout with
`uv sync --no-sources` and `uv run --no-sources pytest`, in addition to local
checks. Editable sibling checkouts alone do not establish release compatibility.

## Runtime boundaries

Qt widgets and model edits run on the GUI thread. Keyboard callbacks enqueue
character presses; MIDI callbacks enqueue MIDI messages. Qt timers consume both
queues and handle deferred GUI work. MIDI input plays notes directly without
character mapping or text recording. Closing MIDI input discards pending messages.
MIDI discovery runs in a background thread only while MIDI is enabled, publishes
a changed port-name snapshot, and never touches widgets directly.

The audio callback is real-time code. Do not put GUI calls, blocking I/O,
logging, model validation, or stream construction in it. Send work to the audio
engine through its command queue.

Note submission prepares voices before the callback consumes them. Recording
copies blocks into a bounded queue; a writer thread drains it. Stopping waits
for queued writes before closing the file and reports write failures or queue
overflow. Callback diagnostics and buffer-setting persistence run when the GUI
polls the engine, or after CLI playback stops. These changes preserve synthesis
and recording samples; they do not guarantee real-time deadlines in Python.

Audio and MIDI use the same route from a `CharPress` through the mapper, scale,
and tuning. Offline rendering constructs an equivalent mixer without opening a
live stream. Keep audio-device, MIDI-device, keyboard, and platform effects at
their package boundaries so unit tests can isolate them.

GUI audio and test-sheet exports render in a spawned process using captured
settings and text. Qt polls progress and owns all widget changes. The parent
owns the temporary output and speech scratch directory, replaces the destination
only after a successful worker exit, and cleans up after cancellation or failure.
Cancel and application shutdown terminate the worker. Native speech synthesis
and frozen application packaging still need platform runtime checks.

## Persistence and units

Text undo stores event edits and recorder timing state. Use `History.text_edit`
around text mutations; supplying the first affected index avoids copying an
unchanged prefix while recording. Whole-configuration edits use snapshots,
and preset undo tracks only the files touched by the preset operation. Undo
history has no fixed depth limit.

Presets are partial TOML or JSON configurations and exclude text. Autosave also
stores text, GUI loop state, and window state. Restore is deliberately tolerant:
invalid saved fields are discarded one at a time so one stale value cannot stop
Tuney from starting.

Quantities accept bare canonical numbers or Pint unit strings. Times use seconds
or milliseconds as their field descriptions specify, frequencies use hertz, and
detuning uses cents. Preserve an authored unit spelling through configuration,
preset, autosave, undo, and file output until the GUI field is edited. Scala
syntax remains Scala syntax and is not parsed as Pint input.

## Change and release checks

Use the smallest change that keeps GUI, CLI, and runtime state consistent. Add a
new musical setting to the relevant Pydantic model first, then let its CLI and
GUI representations derive from that field. Keep runtime-only state cached or
private, never serialized.

After changing Python code or data it uses, run the project checks from the
repository root:

```sh
uv run pytest
uv run ruff check --fix --select B,E,F,I tuney test
uv run ruff format
uv run ty check tuney
version=$(cat .python-version)
version=${version//./}
find test tuney -name '*.py' | xargs uv run pyupgrade --py${version}-plus
git diff --check
```

The automated suite cannot prove physical audio, MIDI, global-keyboard, or
window-manager behavior. Before a release, test typing and replay, changes to
scale/tuning/sound/timing, preset and Scala import/export, WAV export, dark
mode, autosave, resizing, and reconnecting MIDI devices. Check that a missing
selected MIDI output is cleared and reported, and that an output-open failure
disables MIDI output until it is enabled again.
