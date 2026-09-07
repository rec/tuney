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

Tuney requires Python 3.13 or newer. The platform guides install the `tuney`
command from PyPI with pipx:

- [Linux](doc/install-linux.md)
- [macOS](doc/install-macos.md)
- [Windows](doc/install-windows.md)

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

- [Architecture](doc/architecture.md) describes the runtime structure and
  maintenance boundaries.
- [Configuration model](schema.md) is generated from the current Pydantic models
  and checked by the test suite.
- [Tester instructions](doc/tester-instructions.md) cover packaged release builds
  and hardware-dependent checks.
