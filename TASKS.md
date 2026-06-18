## TODO

### Fixup

* Center the Replay button vertically in the section it is in

### Make a plan to split up control_panel.py

###

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
