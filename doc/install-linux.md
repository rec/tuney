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

Tuney needs Python 3.12 or newer. If the number is older, use a newer Linux
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
- Live audio needs working Linux audio output.
- MIDI output is optional and needs a MIDI device or MIDI app.
- Tuney on PyPI: <https://pypi.org/project/tuney/>
- pipx documentation: <https://pipx.pypa.io/stable/>
