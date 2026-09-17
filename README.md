# Tuney: text to music

Tuney is a desktop instrument and command-line program that maps text and live
typing to musical notes. It is intended for musicians and poets who want direct
control over mapping, timing, tuning, synthesis, speech, and MIDI.

## Capabilities

- Play Tuney from the typing keyboard or replay recorded text with its original
  timings.
- Configure character mapping, note names, equal divisions, just intonation,
  ratio tunings, frequency tables, and Scala tunings.
- Synthesize polyphonic audio with selectable waveforms, key scaling, binaural
  beats, optional speech, looping, and randomization.
- Record live output or render text offline to WAV, and export performances as
  Standard MIDI Files.
- Receive and send MIDI, including program, volume, channel, velocity, and MIDI
  Tuning Standard messages.
- Save TOML or JSON configurations, manage partial presets, autosave GUI state,
  and use light or dark mode.

## Install

Tuney requires Python 3.13 or newer. [Using Tuney](doc/using-tuney.md) explains
installation on Linux, macOS, and Windows.

Open the desktop instrument:

```sh
tuney --gui
```

Render text to WAV without opening an audio device:

```sh
tuney --silent --output hello.wav "Hello from Tuney"
```

Write a MIDI file:

```sh
tuney --output hello.mid "Hello from Tuney"
```

Run `tuney --help` for the complete configuration interface, or
`tuney --list-midi` to list the available MIDI inputs and outputs.

## Is this some AI thing?

No. The musical system and algorithms were designed and written by a human. The
later portions of the code were written with the aid of AI coding models and
reviewed by a human.

## Documentation

- [Using Tuney](doc/using-tuney.md) covers installation, the desktop instrument,
  command-line rendering, settings, files, and support.
- [Maintaining Tuney](doc/maintaining-tuney.md) describes the runtime structure,
  project boundaries, and release checks.
- [Configuration model](schema.md) is generated from the current Pydantic models
  and checked by the test suite.

## Development

Run the unit suite in parallel:

```sh
QT_QPA_PLATFORM=offscreen uv run pytest -n auto --dist=loadfile
```

Use `-n 0` to reproduce a failure serially, or replace `auto` with a fixed
worker count such as `2` on a constrained machine. Regenerate regression
fixtures serially with `-n 0 --force-regen`.
