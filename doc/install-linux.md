# Install the Tuney command line on Linux

These steps install Tuney from PyPI, the Python package site. They assume Python,
pipx, audio support libraries, and Tuney are not installed yet.

Linux systems differ. Use the section for your Linux family.

## 1. Open Terminal

Open your applications menu and search for **Terminal**.

Terminal is the app where you type commands.

## 2. Install Python, pipx, and audio libraries

### Ubuntu or Debian

Run:

```sh
sudo apt update
sudo apt install python3 python3-pip pipx libportaudio2
```

### Fedora

Run:

```sh
sudo dnf install python3 python3-pip pipx portaudio
```

### Arch Linux

Run:

```sh
sudo pacman -S python python-pipx portaudio
```

## 3. Check Python

Run:

```sh
python3 --version
```

Tuney needs Python 3.13 or newer. If the number is older, use a newer Linux
release or your distribution's instructions for installing a newer Python.

## 4. Prepare pipx

Run:

```sh
python3 -m pipx ensurepath
```

Close Terminal, then open Terminal again.

## 5. Install Tuney

Run:

```sh
pipx install tuney
```

## 6. Use Tuney

Check that Tuney is installed:

```sh
tuney --help
```

Open the graphical instrument:

```sh
tuney --gui
```

In the graphical app you can play with the typing keyboard, edit the scale and
sound, save presets, browse or import Scala tunings, loop and record a
performance, use MIDI input or output, and switch between light and dark mode.

Render a WAV file from text without playing it live:

```sh
tuney --silent --output hello.wav "Hello from Tuney"
```

The file `hello.wav` will be created in the current folder.

Write the same performance as a MIDI file:

```sh
tuney --output hello.mid "Hello from Tuney"
```

List the MIDI ports Tuney can currently see:

```sh
tuney --list-midi
```

Command-line settings accept the same configuration used by the GUI. Physical
values can include units, for example `--max-gap 2s` or
`--root-frequency 440Hz`.

## Notes

- Live audio needs working Linux audio output.
- MIDI is optional and needs a MIDI device or virtual MIDI application.
- `--config-file` loads a TOML or JSON configuration, and `--preset` loads a
  named preset.
- Tuney on PyPI: <https://pypi.org/project/tuney/>
- pipx documentation: <https://pipx.pypa.io/stable/>
