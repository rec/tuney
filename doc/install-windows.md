# Install Tuney on Windows

These steps install the command-line version from PyPI.

## 1. Install Python

1. Go to the official Python Windows downloads page:
   <https://www.python.org/downloads/windows/>
2. Download the latest Windows installer.
3. Run it.
4. If the installer shows **Add python.exe to PATH**, turn that on.
5. Click **Install Now**.

## 2. Open a command line

1. Click **Start**.
2. Type **PowerShell**.
3. Open **Windows PowerShell** or **Terminal**.

## 3. Install Tuney

Copy and paste these commands one at a time:

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

Close PowerShell, open it again, then run:

```powershell
pipx install tuney
```

## 4. Run Tuney

Try:

```powershell
tuney --help
tuney "Hello from Tuney"
```

Useful links:

- Tuney on PyPI: <https://pypi.org/project/tuney/>
- pipx beginner install notes: <https://pipx.pypa.io/stable/installation/>
