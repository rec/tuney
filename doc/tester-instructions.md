# Tester Instructions

Thank you for testing Tuney. Windows builds are unsigned, and macOS builds are
ad-hoc signed but not notarized. The operating system or antivirus software may
therefore warn before running them.

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

If Tuney reports an error, use **Help > Show Log Location** to find the log file.

## Linux

1. Download `Tuney-<version>-Linux.tar.gz`.
2. Extract the archive.
3. Open the extracted `Tuney` folder.
4. Run the `Tuney` executable from that folder.

Tuney needs working audio and MIDI support on your Linux desktop. If Tuney reports
an error, use **Help > Show Log Location** to find the log file.

## Checksums

Each release includes `.sha256` files for the downloadable builds. Technical testers
can use these to confirm that a downloaded file matches the release asset.

## Basic test

1. Start Tuney and type several letters. Confirm that each mapped character
   lights up and produces sound.
2. Change a scale, tuning, sound, and timing control. Replay the text and confirm
   that the changes take effect.
3. Save and load a preset. Browse the built-in Scala tunings, then import and
   export a `.scl` file.
4. Use the replay and loop controls, then use **File > Save as Audio...** and
   confirm that the resulting WAV file plays.
5. Turn on **View > Dark Mode** and check that the whole window is painted with
   the selected theme.
6. Close and reopen Tuney. Confirm that autosaved settings and window geometry
   are restored.

Speech, MIDI, global background keyboard input, and physical audio-device tests
depend on the hardware and software available on the test computer. Report
which devices and operating-system version were used.

## Platform and device checks

- On macOS, resize from every edge and corner, especially diagonally. Confirm
  that Tuney does not crash, jump after the mouse button is released, or become
  too small to use.
- On Windows, close and reopen Tuney several times. Confirm that its position
  does not drift and that the title bar and menus remain reachable on screen.
- On Windows, check both light and dark mode for unpainted or black background
  areas.
- With MIDI enabled, connect and disconnect input and output devices while
  Tuney remains open. The selectors should refresh without restarting Tuney.
- If the selected MIDI output disappears, Tuney should close it, clear the
  selection, save that change, and display `Output device <device-name> no
  longer exists`.
- If Tuney cannot open an enabled MIDI output, it should show `MIDI output
  failed: error <error text>` and disable MIDI output. Enabling it again should
  retry the connection.

## Reporting a problem

Use **Help > Report a problem...**. Tuney can put its log in a new GitHub issue
and, when selected, save a snapshot of its own window. The issue includes the
local snapshot path, but the tester must attach the PNG manually. Review both
before sharing them because the snapshot can contain visible text and settings
and the log can contain device and configuration details.

For a startup, restore, audio, or MIDI failure, also use **Help > Show Log
Location** and retain the log from the affected run. For a restore problem,
retain the autosave file from the same run as well.
