# Install Tuney on macOS or Linux

These steps install the command-line version from PyPI.

## 1. Open Terminal

On macOS, open **Applications**, then **Utilities**, then **Terminal**.

On Linux, search your apps for **Terminal**.

## 2. Install Python

macOS: install Python from the official downloads page:
<https://www.python.org/downloads/macos/>

Linux: Python may already be installed. Check with:

```sh
python3 --version
```

Tuney needs Python 3.12 or newer. If your version is older, use your Linux
software center or package manager to install a newer Python.

## 3. Install Tuney

Copy and paste these commands one at a time:

```sh
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

Close Terminal, open it again, then run:

```sh
pipx install tuney
```

## 4. Run Tuney

Try:

```sh
tuney --help
tuney "Hello from Tuney"
```

Useful links:

- Tuney on PyPI: <https://pypi.org/project/tuney/>
- pipx beginner install notes: <https://pipx.pypa.io/stable/installation/>
