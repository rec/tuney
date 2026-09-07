# Install the Tuney command line on macOS

These steps install Tuney from PyPI, the Python package site. They assume Python,
pipx, and Tuney are not installed yet.

## 1. Install Python

1. Open <https://www.python.org/downloads/macos/>.
2. Download the latest Python installer for macOS.
3. Open the downloaded `.pkg` file.
4. Accept the defaults and finish the installer.

## 2. Open Terminal

1. Open **Finder**.
2. Open **Applications**.
3. Open **Utilities**.
4. Open **Terminal**.

Terminal is the app where you type commands.

## 3. Check Python

Copy this command, paste it into Terminal, then press **Return**:

```sh
python3 --version
```

Tuney needs Python 3.13 or newer. If the number is older, install a newer Python
from the Python download page above.

## 4. Install pipx

Copy and run these commands one at a time:

```sh
python3 -m pip install --user pipx
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

- MIDI is optional and needs a MIDI device or virtual MIDI application.
- `--config-file` loads a TOML or JSON configuration, and `--preset` loads a
  named preset.
- Tuney on PyPI: <https://pypi.org/project/tuney/>
- pipx documentation: <https://pipx.pypa.io/stable/>
