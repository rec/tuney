# Agent Context: Tuney

This document provides project-specific context for AI agents working on the "tuney" repository. Use this alongside the global AGENTS.md rules.

## 1. What is Tuney?

`tuney` converts text and live typing into musical notes. Waveforms are
synthesized with `numpy` and output with `sounddevice`; MIDI input, output, and
file export use `mido`. Tunings can be computed, ratio-based, frequency tables,
or imported from Scala files. Tuney runs as either a CLI renderer or a PySide6
desktop application.

## 2. Core Tech Stack
- **Language:** Python 3.13
- **Environment Management:** uv
- **Key Dependencies:** pydantic, numpy, PySide6, tyro, sounddevice, mido, pynput

## 3. Project Architecture & Code Map
- `tuney/` - Top level
  - `app/` - CLI entry point, application lifecycle, runtime state, and playback
  - `audio/` - Live and offline audio synthesis, recording, and speech
  - `config/` - The top-level Pydantic configuration model and serialization
  - `keyboard/` - Global keyboard input using `pynput`
  - `mapper/` - Character-to-note mapping
  - `midi/` - MIDI devices, messages, files, listeners, and tuning dumps
  - `presets/` - Preset and autosave persistence
  - `scale/` - Note naming, tunings, ratios, tables, and Scala data
  - `time/` - Text timing and sequencing
  - `ui/` - The PySide6/Qt desktop interface
- `test/` - Unit, integration, and regression tests
- `experiments/`, `scripts/`, and `studies/` - Standalone development tools,
  not production entry points
