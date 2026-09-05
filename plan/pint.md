# Pint Units Plan

## Goal

Accept conventional unit-bearing values wherever Tuney accepts a persisted or
command-line real-world quantity, normalize them to the numeric units used by
audio and sequencing, and write the user's authored unit spelling back to
TOML and JSON when the value is unchanged.

Examples:

- `max_gap = "2 min"`
- `text_timings.space = "0.1 s"`
- `device.sample_rate = "48 kHz"`
- `tuning.root_frequency = "A440 Hz"` is not valid, but `"440 Hz"` is.
- `tuning.detune = "12 cents"`

Runtime audio and sequencing code must continue to receive ordinary `float` or
`int` values in its established canonical units. Unit strings are an input and
persistence concern, not a replacement for Tuney's numerical calculations.

## Reccy Prerequisite

Reccy's `configuration.units.Seconds`, `Milliseconds`, and `Hertz` already parse Pint
quantities, preserve authored provenance, and provide `authored_dump()` and
`revalidation_dump()`.

Pint's default registry does not define musical cents. Add a Reccy
`MusicalCents` annotation in a separate Reccy change. It should define a
dimensionless musical-cent unit as one 1200th of an octave, accept `cent` and
`cents` aliases, normalize to cents, reject dimensional quantities, and retain
the existing no-unit numeric input. Add unit tests for `"100 cents"`, a bare
number, incompatible units, and authored-dump round trips. Do not reinterpret
Scala files: their decimal cent notation and ratio expressions have Scala
specific semantics.

Before changing Tuney, verify whether `Hertz` can retain the integer type
required by `Device.sample_rate`. If it cannot, add and test a Reccy
whole-hertz annotation rather than silently making a sample rate a float.

## Unit Inventory

Convert externally configured quantities as follows.

| Area | Fields | Canonical unit |
| --- | --- | --- |
| Top-level timing | `Tuney.max_gap`, `hover_time`, `backspace_repeat_delay` | seconds |
| Text timing | `TextTimings.space`, `dot`, `comma`, `colon`, `semicolon`, `blank_line`, `overlap`, `other`, `timings`; `CharPress.time` | milliseconds |
| Replay and speech timing | `LoopState.before`, `LoopState.after`, `SpeechPhrase.start`, `KeyRecorder.start_time`, `time_offset`, `insert_time` | seconds for loop/speech/start time; milliseconds for recorded-event offsets |
| Synth duration | `Sound.minimum_note_time`, `Voice.fade_in`, `fade_out`, `minimum_note_time` | seconds |
| Frequencies | `Device.sample_rate`, `Binaural.frequency`, `Tuning.root_frequency`, `Voice.frequency`, and absolute entries in `Table` | hertz |
| Tuning offset | `Tuning.detune` | musical cents |

Keep dimensionless values as plain numbers: gains, widths, ratios,
polyphony/headroom, playback tempo and scales, note numbers, character counts,
sample/frame counts, MIDI values, and speech speed. They are not physical
quantities with an unambiguous Pint unit.

## Implementation Steps

1. Add the Reccy musical-cent annotation and, only if necessary, whole hertz
   support. Release or update the editable Reccy checkout first, then refresh
   Tuney's lockfile only if Reccy's declared dependencies change.
2. Replace Tuney's local `Seconds` and `Milliseconds` aliases with the Reccy
   annotations. Introduce narrow local imports for `Hertz` and
   `MusicalCents`; do not create duplicate unit validators in Tuney.
3. Apply the annotations to the inventory above. Retain each field's existing
   Pydantic bounds and UI `Numeric` metadata so values are converted before
   existing range validation.
4. Make all CLI unit fields use `reccy.configuration.tyro.unit_spec(...)` through the
   existing `tyro_option` metadata. This must let `tuney --max-gap 2s` and
   `tuney --tuning.root-frequency 0.44kHz` validate identically to TOML input.
   Keep CLI help metavariables explicit about the canonical unit.
5. Replace direct numeric parsing in `app/text_timing.py` and
   `ui/replay_controls.py` with `pydantic.TypeAdapter` instances for their
   respective unit annotations. This makes editable timing fields accept values
   such as `"250 ms"` and `"1:30"` without changing their internal units.
6. Add a table-value parser path that accepts a complete Pint hertz quantity
   such as `"440Hz"`, while retaining existing arithmetic and ratio expression
   evaluation. Do not pass arbitrary expression fragments to Pint and do not
   change Scala parsing.
7. Preserve authored values through state transitions and writes. Use
   `reccy.configuration.units.authored_dump()` at Tuney's user-facing persistence boundaries:
   presets, autosave, exported configuration, audio-file comments, and tuning
   export where applicable. Use `revalidation_dump()` whenever an existing
   model is copied then revalidated, so unrelated UI edits do not turn
   `"2 min"` into `120`.
8. Keep GUI numeric controls canonical. A spin box may display `120` for an
   authored `"2 min"`; editing it replaces that field's provenance with the
   entered numeric value. Free-text timing controls retain the ability to enter
   units. Do not add a second formatting system to the control panel.
9. Update help and maintained documentation with accepted syntax, canonical
   internal units, and persistence behavior. Remove obsolete local aliases and
   conversion tests only after callers have migrated.

## Tests and Verification

- Add Reccy-side tests for musical cents and any whole-hertz addition.
- Add Tuney model tests for seconds, milliseconds, hertz, and cents from bare
  numbers and unit strings, including incompatible-unit failures.
- Cover nested `TextTimings` containers, recorded `CharPress` values, speech
  phrase starts, loop windows, and sample rates.
- Cover CLI parsing through Tyro and free-text UI parsers without launching the
  full GUI.
- Regression-test authored persistence across presets, autosave, JSON export,
  TOML output, undo/redo snapshots, and a model revalidation after an unrelated
  change. Assert runtime values remain numeric and existing audio calculations
  receive their current canonical units.
- Run the Reccy suite before its commit. For Tuney, run `uv run pytest`, Ruff,
  formatting, `uv run ty check tuney`, pyupgrade, and `git diff --check`.

## Commit Structure

1. Reccy: add and test musical cents, plus whole hertz only if required.
2. Tuney: add unit annotations and parsing at model, CLI, and editor boundaries.
3. Tuney: preserve authored unit values in persistence and add regression tests.
4. Tuney: document unit syntax after the behavior is verified.

## Additional Work Beyond the Prompt

None.
