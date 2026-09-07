# Tuney Architecture

Tuney is a Python 3.13 application that maps typed characters to note numbers,
turns those notes into synthesized audio and optional MIDI, and provides the
same configuration model to both a Qt GUI and a command-line renderer.

## Entry Points

`tuney.app.main:main` is the installed `tuney` command. It parses command-line
arguments into an `App`, overlays a selected preset or configuration file, and
then dispatches to GUI or CLI mode.

- GUI mode creates one Qt `MainWindow`, restores autosave state when allowed,
  starts input and MIDI services, and enters the Qt event loop.
- CLI mode requires text and either plays it, records the live performance to
  WAV, renders WAV offline with `--silent`, or writes a Standard MIDI File,
  without constructing the GUI.
- `--list-midi` is handled before normal application startup, so it can inspect
  MIDI ports without opening a window or audio device.

## Application Model

The application is a mutable Pydantic model with this inheritance chain:

```text
App
  AppPlayback
    AppState
      AppMembers
        Tuney
          BaseModel
```

`Tuney` owns user-visible musical and runtime configuration: mapper, scale,
tuning, audio device and sound settings, MIDI settings, timing, text, and
mode-specific options. `AppMembers` supplies cached runtime collaborators.
`AppState` owns configuration replacement, persistence, randomization, and
cache invalidation. `AppPlayback` turns character events into audio and MIDI
actions and implements CLI rendering. `App` owns the top-level lifecycle.

The model is intentionally mutable while the GUI is active. A control edit is
validated by reconstructing the affected model and copying its validated field
value back to the live object. When a setting changes, dependent cached runtime
objects are discarded or explicitly reconfigured. Do not make `App` or `Tuney`
frozen without replacing this update model.

## Musical Data Flow

```text
text or key event
  -> CharPress
  -> Mapper
  -> note number
  -> Scale + Tuning
  -> frequency
  -> Player / MIDI output
```

`CharPress` carries a character, press/release state, and timestamp.
`TextTimings` creates press sequences for plain text, and `Sequencer` replays
them. `Mapper` maps characters to note numbers. `Scale` assigns note names and
uses `Tuning` to calculate frequencies.

For synthesized sound, `Player` maintains pressed notes and sends note commands
to one `AudioEngine`. The engine owns the output stream and a `Mixer`, which
renders active voices in the audio callback. Offline rendering constructs an
equivalent mixer and writes file output without opening the live stream.

`MidiOut` translates note events to MIDI messages independently of synthesized
audio. It can send program and volume changes at startup and a MIDI tuning dump
when configured. `MidiIn` routes incoming note events through `MidiListener` to
the same playback path used by keyboard input. Speech can accompany replayed
text and is mixed into live or offline audio output.

## Runtime Boundaries

| Area | Responsibility | Main modules |
| --- | --- | --- |
| Configuration | Pydantic models, annotations, CLI metadata, serialization | `tuney/config/` |
| Mapping and tuning | Character mapping, scale definitions, ratios, Scala import | `tuney/mapper/`, `tuney/scale/` |
| Timing | Character event recording and replay | `tuney/time/`, `tuney/app/key_recorder.py` |
| Audio | Voices, mixing, live output, offline files, speech | `tuney/audio/` |
| MIDI | Port discovery, input, output, files, tuning dumps | `tuney/midi/` |
| Input | Global keyboard listener and modifier handling | `tuney/keyboard/` |
| Persistence | Presets, autosave, JSON/TOML conversion | `tuney/presets/`, `tuney/config/serialize.py` |
| UI | Qt window, generated controls, note grid, transport, dialogs | `tuney/ui/` |
| Platform support | Paths, logging, crash reporting, single-instance behavior | `tuney/app/platform_info.py` |

The UI is a consumer of `App`; it does not own a parallel configuration model.
Qt controls read `Annotated` display metadata from Pydantic fields and send
validated edits back to the same live objects used by CLI and playback.

## GUI Concurrency

Qt widgets and model edits run on the GUI thread. Keyboard and MIDI callbacks
place `CharPress` events on queues consumed by `MainWindow`. Qt timers handle
queue polling, delayed callbacks, transport updates, and deferred resize work.

MIDI device discovery runs every two seconds in a background thread, and only
while MIDI input or output is enabled. It publishes a new port-name snapshot to
the GUI queue only when the available devices change. The GUI then refreshes
its selectors; if the selected output disappears, Tuney closes it, clears the
saved selection, and tells the user. The background thread must not manipulate
Qt widgets directly.

The audio callback is a separate real-time boundary. Keep GUI calls, blocking
I/O, logging, model validation, and stream construction out of it. Commands
cross into the audio engine through its command queue.

## Persistence and Recovery

Tuney reads configuration from TOML or JSON. Presets are partial configurations
stored in built-in and user preset directories; text-related fields are excluded
from presets. Autosave persists the current configuration plus GUI-only loop and
window state. Global GUI preferences such as theme and control-panel layout are
stored separately. Autosave restores only for a normal GUI launch without an
explicit text, preset, or configuration source. Restored window geometry is
adjusted to keep the top of the window reachable on an available screen, and a
deferred application-level minimum protects the controls without relying on Qt
top-level minimum-size constraints.

The platform layer configures Reccy logging and maintains crash markers under
the user state directory, guards GUI startup with a single-instance lock, and
offers issue reporting after a detected crash. A report can include the log and
can save an optional snapshot captured from Tuney's own window. The generated
issue includes the snapshot's local path so the user can attach it. Autosave
parsing is deliberately tolerant of individual invalid fields so an old or
damaged state file does not prevent the application from starting.

## Units

Configured physical quantities accept either bare numbers in Tuney's canonical
units or Pint unit strings. Time settings use seconds or milliseconds according
to their field descriptions, frequencies use hertz, and tuning detune uses
musical cents. For example, `--max-gap 2min`, `--root-frequency 0.44kHz`, and
`--text-timings.space 0.1s` are equivalent to their canonical numeric values.
CLI help identifies each unit-bearing option's canonical unit.

Tuney normalizes these values before audio and sequencing code receives them.
When a unit-bearing value has not been edited, configuration exports, presets,
autosave, undo snapshots, and audio-file settings retain its authored spelling.
Editing a GUI numeric control replaces that field with its displayed canonical
number. Scala files retain their own decimal-cent and ratio syntax and are not
parsed as Pint quantities.

## Extension Guidelines

- Add a musical setting to the relevant Pydantic model first. Its CLI and GUI
  representation should derive from that one field.
- Keep runtime-only objects as cached properties or private runtime state, not
  serialized configuration fields.
- Route user-facing edits through validation and cache invalidation rather than
  mutating nested state ad hoc.
- Keep device and platform effects behind the audio, MIDI, keyboard, and
  platform modules so they can be isolated in tests.
- Prefer an additional focused UI helper over adding application behavior to a
  widget class when the same behavior is needed by CLI or background input.
