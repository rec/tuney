# Agent Context: Tuney

This document provides project-specific context for AI agents working on the "tuney" repository. Use this alongside the global AGENTS.md rules.

## 1. What is Tuney?

`tuney` converts text into musical notes. Each character in the text generates a specific freqency.
Waveforms are synthesized using `numpy` and output using `sounddevice`.
The user can either play live with a typing keyboard, or pass in text to be turned into notes.
Note scales are highly customizable, with possibilities of just or n-tet tunings and different note names.
`tuney` is run as a CLI from the command line, but brings up a GUI.

## 2. Core Tech Stack
- **Language:** Python 3.12
- **Environment Management:** uv
- **Key Dependencies:** pydantic, numpy, tyro, sounddevice, pynput

## 3. Project Architecture & Code Map
- `tuney/` - Top level
  - `audio/` - Synthesizes and plays audio using `numpy` and `sounddevice`
  - `cli.py` - Runs the CLI using `tyro`
  - `keyboard/` - Handle keyboard input using `pynput`
  - `mapper/` - Map characters to note numbers
  - `scale/` - A `Scale` maps note numbers to frequencies, and can convert note numbers to and from string names
  - `time/` - Handles sequencing, and also representing how plain text without timings is assigned timings
  - `tuney.py` - The top level `pydantic.BaseModel` which contains the whole configuration
  - `ui/` - A `tkinter` GUI using the `customtkinter` package
- `tests/` - Contains unit and integration tests.
- `scripts/` - Experimental scripts that are to be ignored
