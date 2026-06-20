# Feature Proposal: Performance Presets

Tuney would benefit from a first-class concept of a performance preset: a named,
shareable configuration that captures the musical identity of a piece without
requiring the user to hand-edit every low-level parameter each time. A preset
would bundle the mapper, scale, tuning, oscillator, MIDI settings, text timing
settings, and output-related defaults into a single named profile that can be
loaded from the command line or selected in the GUI.

The main value is that Tuney already has a rich configuration surface, but that
richness can make exploration slow. A user might want one setup for bright
diatonic live typing, another for dense chromatic MIDI output, and another for
slow spoken-text rendering with long overlaps and a soft waveform. Today those
settings exist, but the user has to remember or preserve them as whole config
files. Presets would make the common workflow explicit: choose a sound world,
type or render text, then save the result.

A useful initial version would not need a large preset manager. It could start
with a small `presets/` directory containing TOML files, a `--preset NAME`
command-line option, and a GUI pulldown that lists bundled and user presets.
Selecting a preset would load those fields into the current `Tuney` model. Saving
a preset could reuse the existing config serialization path and write only the
configuration fields, not recorded `CharPress` text data. That keeps presets
separate from compositions.

This would also give the project a better way to demonstrate its range. Bundled
presets could show practical starting points such as `white-notes`, `twelve-tet`,
`just-intonation`, `midi-controller`, and `ambient-text`. These examples would
act as documentation without requiring a tutorial. They would also make manual
testing easier, because a known preset can define a stable set of parameters for
checking playback, GUI layout, MIDI routing, and file rendering.

The implementation should stay conservative. A preset should be the same data
shape that Tuney already saves, loaded through the same validation path. If a
preset omits a field, the normal model default should apply. If a preset includes
recorded text, that should probably be rejected or ignored at first so presets do
not blur into project files. The first version should avoid inheritance, preset
composition, search paths, package discovery, or migration logic. A single user
directory plus bundled presets would be enough.

This feature fits the current program because it does not change what Tuney is.
It makes the existing configurability easier to use, easier to demonstrate, and
easier to return to. It would help both live users, who want a quick playable
setup, and command-line users, who want repeatable rendering without long option
lists.
