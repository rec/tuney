# Install the Tuney command line on Windows

These steps install Tuney from PyPI, the Python package site. They assume Python,
pipx, and Tuney are not installed yet.

## 1. Install Python

1. Open <https://www.python.org/downloads/windows/>.
2. Download the latest Python installer for Windows.
3. Open the downloaded installer.
4. Turn on **Add python.exe to PATH** if the installer shows that checkbox.
5. Click **Install Now** and finish the installer.

## 2. Open PowerShell

1. Click **Start**.
2. Type **PowerShell**.
3. Open **Windows PowerShell**.

PowerShell is the app where you type commands.

## 3. Check Python

Copy this command, paste it into PowerShell, then press **Enter**:

```powershell
py --version
```

Tuney needs Python 3.13 or newer. If the number is older, install a newer Python
from the Python download page above.

## 4. Install pipx

Copy and paste these commands one at a time:

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

Close PowerShell, then open PowerShell again.

## 5. Install Tuney

Run:

```powershell
pipx install tuney
```

## 6. Use Tuney

Check that Tuney is installed:

```powershell
tuney --help
```

Open the graphical instrument:

```powershell
tuney --gui
```

In the graphical app you can play with the typing keyboard, edit the scale and
sound, save presets, browse or import Scala tunings, loop and record a
performance, use MIDI input or output, and switch between light and dark mode.

Render a WAV file from text without playing it live:

```powershell
tuney --silent --output hello.wav "Hello from Tuney"
```

The file `hello.wav` will be created in the current folder.

Write the same performance as a MIDI file:

```powershell
tuney --output hello.mid "Hello from Tuney"
```

List the MIDI ports Tuney can currently see:

```powershell
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
