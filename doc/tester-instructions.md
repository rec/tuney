# Tester Instructions

Thank you for testing Tuney. These builds are unsigned, so Windows and antivirus
software may warn before running them.

## Downloads

Use the files attached to the GitHub release:

- Windows: download `Tuney-<version>-Windows.zip`.
- macOS: download `Tuney-<version>-macOS.zip`.
- Linux: download `Tuney-<version>-Linux.tar.gz`.

Do not download the "Source code" files unless you want to install Tuney from Python.

## Windows

1. Download `Tuney-<version>-Windows.zip`.
2. Right-click the zip file and choose **Extract All...**.
3. Open the extracted `Tuney` folder.
4. Double-click `Tuney.exe`.

Do not move `Tuney.exe` out of the folder. It needs the files next to it.

If antivirus software quarantines Tuney, restore it only if you trust that you got the
file from the official Tuney GitHub release. Some antivirus tools flag unsigned
PyInstaller applications even when they are harmless.

For repeated testing, create a dedicated folder such as:

```text
C:\Users\<name>\Apps\Tuney
```

Then add that folder as an allowed or excluded folder in your antivirus software.

## macOS

1. Download `Tuney-<version>-macOS.zip`.
2. Open the zip file.
3. Right-click `Tuney.app` and choose **Open**.
4. If macOS asks for confirmation, choose **Open** again.

## Linux

1. Download `Tuney-<version>-Linux.tar.gz`.
2. Extract the archive.
3. Run the `Tuney` executable from the extracted folder.

## Checksums

Each release includes `.sha256` files for the downloadable builds. Technical testers
can use these to confirm that a downloaded file matches the release asset.
