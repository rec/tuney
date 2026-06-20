## TODO

### Limit modes for notes: wrap around and reflect

#### centering issue

### Better layout for the control panels

### Beginner and advanced modes

### Have a preloaded library of scales

## DONE
### Clean up control_panel.py

* The fields in the waveform and function radio buttons should be closer together
* In Scale, move `end` and `offset` to the end of the first line
* In Mapper, move `offset` to right after `length`
* The three top-level fields, the two Player fields, and pitch_to_frequency.function should all be grouped together in a section at the top called 'general'
* In MIDI, if enable is off, then the rest of the fields should be greyed out and disabled.
* In Device, hide the channels member from both the GUI and the command line

### Fixup

* Make the control panel 20% taller and the Text region below it 20% smaller
* Get rid of the empty player section.
* Put all the controls for Device on one line.
* In text_timings, make all the text boxes on the first line one chracter thinner.
* Rename `random_seed` to `seed` everywhere
* The greying out of the MIDI section when it is disabled needs to be much more

### Fixup:

* The fields MIDI should be greyed out, not by going darker, but by going lighter.
* The tuning section has a darker background for its title. Change all the other section to do the same
* Make the control panel about 25% bigger

### Fixup:

* Make dtype into a pulldown menu
* In the MIDI greying out, the caption has to get a lot lighter

### Fixup:

* When MIDI is disabled, the captions in the MIDI segment have to get a lot lighter.

### Fixup:

* When MIDI is disabled, the captions channel, velocity and note_offset in the MIDI segment of the GUI have to get a lot lighter.
* Codex did a bad job on this.

### Rename some variables in Tuney

Making sure there aren't any conflicts with existing names, in both the GUI and the CLI, rename:

* notes_used -> notes
* limit_denominator -> limit
* octave_divisions -> notes_per_octave
* octave_change -> octave_ratio

### When the grid gets resized, the edges of the note names get cut off

Fix this by making the note name font smaller at small button sizes

### Fixup

The previous commit introduced two issues:

1. The font is tiny when it starts up
2. When you resize the app to be larger, it stops responding.

Fix the last change so the scaling only kicks in when the Note is below a certain size. Give me a single parameter that I can experiment with for how much scaling there is, so I can experiment and adjust it by hand.

### Fixup

Two more issues:

1. The fonts need to be about 25% bigger at all levels.
2. The scaling should also handle height, as well as width: when the height gets small, the labels get cut off.

### If seed is not set, pick a seed by calling random.randint, using it to set the randomizer seed, and storing it in

### Add an accelerator to the File/Refresh command

Rename it to File/Refresh Devices and use command-D.

### Move the area containing the Replay button to above the note_grid, and make sure that it's of fixed height.
### In control_panel, fix the types of `values` and `value`, which are currently Any

### Fixup

Inline OptionValues

### Fixup

The region containing the Replay button needs to be 30% shorter, and the Replay button
should be centered in both height and width.

### Fixup

* Make the Replay button 50% taller
* Center it vertically in the section it is in

### Move layout constants to their own file.

Bring the constants PAD and QUARTER, and all the constants in control_panel.py, into a new file, ui/constants.py. Do not import individual constants from this file; always import just the symbol `constants`.

### Consolidate tables in constants.py

In a new commit, consolidate the first three dicts in constants.py into one dict whose value is a new data class.

### Fixup: change ControlConfig to use lists instead of tuples, sets or frozensets

### Create data classes for the constants and read it from a file

In a new commit, create one data classes that represents all the constants
in constants.py, perhaps with other data ckasses foir

### Make a plan to split up control_panel.py

## Remove multiprocessing mode and all references to it

### Move ControlPanel.refresh_devices to Layout

### Write a plan for better audio

#### Goals

* Use shared memory and numpy arrays and subprocess or multiprocess.
* Have each oscillator render in a process separately.
* Have another process sum all these oscillators: it should be at least 0x2000 or 8192
  samples ahead of real time
* Be able to record audio files on the fly
* Be able to render audio to file without playing it, faster than real time

Write a plan to implement the above Goals. Describe the overall approach in a couple of paragraphs, then try to partition the solution into two to four separate, self-contained commits.

Store this plan in BETTER_AUDIO.md and commit it.

### Fixup

* Turn OfflineRenderer into a data class
* Reread AGENTS.md and use that information to rewrite the audio unit tests as regression tests

### Notes should have a minimum time length

There should be a configurable `minimum_note_time: float = 0.5` which controls how short note playback can be
and applies to notes from the keyboard, button, or being replayed.

Tuney.char_presses will be unchanged: this only happens during playback.

### Add CLI mode

* Rename disable_gui to cli

If cli is True:
    * Fail if char_presses is non-empty or disable_sound
    * Do not bring up a GUI
    * Play back the note generated by char_presses
    * Exit the application

### Rename disable_sound to silent

### Output audio in CLI mode to a file

* Add a new field `output` that expects a Path to an audio file name (e.g. out.wav)
* Forces --cli mode if `output` is set.
* Fails if there is no text to play.
* If --silent is set, it directly outputs the audio to the file, otherwise it plays back sound at the same time that it writes audio to the file.
* If the program is interrupted with control-C before it has finished writing, the partial output file is removed.

### Add two transport buttons to the GUI

Create a Transport widget with two buttons, `record` and `stop`

The buttons will have graphic images on them, SVG if this is possible.

There will be four images:

1. record-imege: a red filled-in circle
2. disabled-stop-image: a grey filled-in square.
3. stop-image: a black filled-in square.
4. pause-image: a red pause symbol

A Transport has three states:

1. State `read`

The button `record` shows record-image, and `stop` is disabled and shows disabled-stop-image
Clicking on `record` changes the state to `recording`.

2. State `recording`

The button `record` shows pause-image, and `stop` is enabled and shows stop-image.
Clicking on `record` changes the state to `paused`, clicking `stop` changes the state to `ready`.

3. State `paused`

The button `record` shows record-image and `stop` is enabled and stop-image.
Clicking on `record` changes the state to `recording` and clicking `stop` changes the state to `ready`.


Transport will take a callback that accepts a State.


# * Put it on the left side of the same panel containing the replay button

### Add hover overs to every widget

* Add a new config: `hover_time: float = 1`, meaning 1 second.
* If the user hovers over a widget for more than a this time, bring up text.
* Hover-over text is taken from the help or doc comment for the widget, in exactly the same way that `tyro` does it.

### The positional arguments to `tuney` should make up `text`.

config_file should not be a positional argument anymore.

Instead the positional arguments to `tuney` should be joined together with spaces, and used to populate `text`.

If Tuney already has non-empty `char_presses`, those should be discarded.

### Make cli mode the default

* Rename --cli to --gui and negate it, so `tuney Hello world` does not bring up a GUI
* If `char_presses` is empty in cli mode, print a usage message and exit with a non-zero code.

### Allow subsets of the scales to be used ("white note mode")

* This is partly implemented already, and will use the existing unused "notes" config field.
* The field is a string containing note names, which can be split by Scale._to_notes
* If this is set by the user, then only those notes are allowed in the scale and can be triggered by a CharPress
* This doesn't change any frequencies of note names, but prevents some notes from being used or enumerated.
* The canonical example is "white notes" - setting `notes` to be "ABCDEFG".

### Enable audio recording in GUI mode

* When Transport's state switches from ready to recording, start recording audio.
* When it changes from recording to pause, stop recording but keep the data
* When it change state to ready again, bring up a new file dialog and save the audio to that file.
* If they cancel on the file dialog, keep the audio, and remain in the original state.

### Add a Clear button to Transport

* Add a Clear button with two images: clear-image and disabled-clear-image.
* In state ready, the Clear button is disabled.
* In state recording or paused, the Clear button is enabled, and changes the state to ready.
