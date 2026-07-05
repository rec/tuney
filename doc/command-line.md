# Command Line Cleanup Plan

## Goal

Make `tuney --help` easier to scan and make every configurable setting reachable
with a unique, short, predictable command-line name.

## Problems To Solve

1. Nested configuration names are long, for example `--sound.oscillator.period`.
2. Some leaf names repeat across the model, for example `note_offset`, `gain`, and
   `device`, so flattening names requires a collision rule.
3. Common commands should have short aliases.
4. Every visible command-line option should have a single-character alias.
5. Config-file field names may change. There is no compatibility requirement for
   old config files.

## Phase 1: Inventory Current Options

Generate the current tyro option list from `Tuney`, excluding suppressed fields.
Record each option with:

* Full tyro path
* Leaf field name
* Data class owner
* Type
* Current help text
* Whether it is hidden from the GUI
* Proposed model field path
* Proposed long flag
* Proposed short flag

Use this inventory to find duplicate leaf names before changing code. Prefer
renaming model fields so the config file and command line use the same cleaned-up
names.

## Phase 2: Choose Unique Long Names

Prefer unprefixed long names when the leaf name is unique and clear:

* `--gui`
* `--silent`
* `--output`
* `--max-gap`
* `--hover-time`

For duplicate or ambiguous leaves, use a short domain prefix instead of the full
model path:

* `--audio-device`
* `--midi-output`
* `--audio-note-offset`
* `--midi-note-offset`
* `--oscillator-period`
* `--oscillator-duty-cycle`
* `--scale-root`
* `--mapper-range-limit`

Keep full nested names out of the primary help output. Rename the underlying
model fields where that makes the CLI and config file simpler. Do not preserve
old nested names or old config keys unless keeping one of them is genuinely
simpler than removing it.

## Phase 3: Assign Single-Character Short Options

Assign single-character aliases only after the long names are final. Reserve the
most obvious letters for the most common top-level commands:

* `-g`, `--gui`
* `-s`, `--silent`
* `-o`, `--output`
* `-p`, `--preset`
* `-c`, `--config-file`
* `-b`, `--run-in-background`

Then assign remaining letters by subsystem. Prefer mnemonic letters when they do
not collide, and use uppercase letters only when the lowercase form is already
used. The final alias table should be explicit in code and covered by a help
regression test.

## Phase 4: Implement With tyro Metadata

Use `Annotated[..., tyro.conf.arg(...)]` on model fields to define:

* `name`
* short aliases
* help text

Do not add a custom parser unless tyro cannot express the alias table. Prefer
real model-field renames over command-line-only aliases so saved config files,
the GUI control panel, and CLI help all use the same vocabulary.

## Phase 5: Update Tests

Update the existing help-output regression test to include the new long and short
flags. Add targeted tests for:

* No duplicate public long flags
* No duplicate short flags
* Common aliases parse into the expected model fields
* Config-file loading uses the new field names
* Old config field names are not accidentally accepted unless explicitly listed

## Phase 6: Documentation Pass

Update user-facing documentation after the implementation lands. Keep the docs
focused on practical command examples rather than listing every generated option.

## Additional Work Beyond The Prompt

None.
