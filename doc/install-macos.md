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

Tuney needs Python 3.12 or newer. If the number is older, install a newer Python
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

## 6. Run Tuney

Check that Tuney is installed:

```sh
tuney --help
```

Create a WAV file from text:

```sh
tuney --silent --output hello.wav "Hello from Tuney"
```

The file `hello.wav` will be created in the current folder.

## Notes

- To open the graphical app from the command line, run `tuney --gui`.
- MIDI output is optional and needs a MIDI device or MIDI app.
- Tuney on PyPI: <https://pypi.org/project/tuney/>
- pipx documentation: <https://pipx.pypa.io/stable/>
