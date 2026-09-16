# Using Tuney

Tuney turns typed text into notes. Use the graphical instrument to play and
shape a performance, or use the command line to play, record, or render text.

## Start here

Tuney needs Python 3.13 or later and [pipx](https://pipx.pypa.io/stable/).
Set up these prerequisites before installing Tuney.

On macOS, install a current Python from [python.org](https://www.python.org/downloads/macos/)
first, then install pipx with:

```sh
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

On Windows, install a current Python from [python.org](https://www.python.org/downloads/windows/),
select **Add python.exe to PATH**, then run in PowerShell:

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

On Linux, install Python, pipx, and PortAudio with the package manager, then
run `python3 -m pipx ensurepath`. For example:

```sh
# Ubuntu or Debian
sudo apt install python3 python3-pip pipx libportaudio2

# Fedora
sudo dnf install python3 python3-pip pipx portaudio

# Arch Linux
sudo pacman -S python python-pipx portaudio
```

Check that `python3 --version` (or `py --version` on Windows) reports at least
3.13. A Linux distribution's default Python may be older; install a supported
Python first if necessary.

Restart the terminal after `ensurepath`, then install Tuney and check it:

```sh
pipx install --python python3 tuney
tuney --help
```

On Windows, use `pipx install --python python tuney`. If multiple Python versions
are installed, pass the path to the Python 3.13-or-later executable to `--python`.

## Play in the graphical instrument

Start Tuney with:

```sh
tuney --gui
```

Type to add text and play its mapped notes. The controls change the mapping,
scale, tuning, timing, sound, and MIDI settings used by the same live
performance. Use the transport controls to replay text and loop a selected
range. **Edit** offers undo, redo, randomization, and clearing; **View** offers
dark mode, advanced controls, and recorded text timings.

Copying and pasting text within Tuney preserves recorded press/release timing.
Plain text from another application uses the current text timing settings.

Use **File** to open a text file, save configuration, save a preset,
import or export a Scala tuning, and save the current text as audio. Tuney
autosaves the GUI configuration, text, loop state, and window position. That
autosave is restored only for an ordinary GUI launch, not when you give text, a
preset, or a configuration file on the command line.

Audio and test-sheet exports show progress and a Cancel button. They use the
text, settings, and selected presets captured when export starts. Cancelling
leaves any existing destination file intact, as does a failed export.

Global keyboard input is optional. Turn on **Run in Background** only when you
want Tuney to receive typing while another application is active.

## Use the command line

Pass text positionally to play it:

```sh
tuney "Hello from Tuney"
```

The same text can be supplied with `--text`. `--gui` opens the desktop
instrument; without it, a command with text runs in command-line mode.

Render a WAV file without opening a live audio device:

```sh
tuney --silent --output hello.wav "Hello from Tuney"
```

Write a Standard MIDI file by choosing a MIDI filename:

```sh
tuney --output hello.mid "Hello from Tuney"
```

MIDI filenames (`.mid`, `.midi`, or `.smf`) export without live playback.
For audio files, `--output` records live playback unless `--silent` is given.
Use `--list-midi` to print available MIDI inputs and outputs as JSON.

Every musical setting is available to both the GUI and the command line. Run
`tuney --help` for the current option names and descriptions. Values with units
accept either Tuney's ordinary numeric unit or a unit string, for example:

```sh
tuney --max-gap 2s --root-frequency 440Hz "text"
```

## Shape the music

The signal path is:

```text
text or key event -> character map -> scale -> tuning -> audio and MIDI
```

The mapper assigns characters to note numbers. The scale supplies note names;
the tuning turns note numbers into frequencies. Choose a computed equal-division
tuning, a ratio tuning, a finite frequency table, or a Scala tuning. A finite
table has a fixed range, but Tuney wraps instrument keys before using it so
typing remains playable.

The sound controls select the oscillator and its gain, polyphony, minimum note
duration, binaural beats, and output level. Enabled speech accompanies GUI replay,
CLI playback, and audio exports. Speech finishes even when it outlasts the notes;
replay loops wait for it before restarting. Explicit Stop cancels speech.
MIDI input plays notes directly without adding recorded text. MIDI output can send note
events, program and volume changes, and a MIDI Tuning Standard dump when
configured.

MIDI input channel `omni` accepts every channel. For MIDI output, the same
stored value uses channel 1; it does not broadcast to every channel.

## Save and share settings

Configuration files are TOML or JSON and can contain the complete configuration:

```sh
tuney --config-file performance.toml "text"
```

Presets are named partial configurations. Select one in the GUI or load it with:

```sh
tuney --preset white-notes "text"
```

Presets do not contain text. User presets are stored in `~/.config/tuney/presets`
on every platform, where `~` means your home directory; built-in presets remain available
as fallbacks. The generated [configuration model](../schema.md) gives the full
data shape for hand-written configuration files.

## Packaged releases and problem reports

Close older tuney processes before launching an updated version. Instance
ownership now uses an OS lock; older PID-file claims do not coordinate with it.

Release builds are attached to GitHub releases. Download the platform archive,
extract it, and run the contained application without moving it out of its
folder. Windows builds are unsigned and macOS builds are ad-hoc signed but not
notarized, so the operating system or antivirus software may ask for confirmation.
On macOS, right-click the app and choose **Open** the first time.

For an audio, MIDI, startup, or restore problem, use **Help > Show Log
Location**. **Help > Report a problem...** can prepare a GitHub issue and save
a window snapshot. Review the log and snapshot before sharing: they may contain
device details, visible text, or settings. Hardware-dependent reports should
include the operating-system version and the audio and MIDI devices involved.
