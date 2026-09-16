# Tuney issues

Reviewed 2026-09-16 against Tuney commit `1aab15a` by reading implementation,
tests, documentation, dependency declarations, and release configuration.
Implementation authorized on 2026-09-16. Completed items retain their original
evidence below and are marked with their resolution.

Evidence below is from source inspection unless stated otherwise. No application,
hardware test, release build, or test suite was run for this documentation-only
review. Previous passing suites do not establish that the edge cases below work.
The remote issue tracker was not reconciled. This is a broad review, not an
exhaustive audit of every file.

P1 means potential data loss or an important runtime defect; P2 means a behavioral
bug, usability trap, or material performance risk; P3 means maintenance or naming
debt. Each item includes a next step, which still needs implementation review.

Tuney's permissive scale editing behavior is authoritative. Accepting zero
intervals and retaining unknown note text for UI feedback are intentional, not
issues to fix by reinstating stricter Ufor validation.

## P1: data safety and runtime correctness

### 1. Failed CLI export can delete an existing destination

**Resolved:** CLI audio/MIDI and GUI exports use temporary destination-side
files and replace the destination only after successful writer cleanup.
Recorded-audio Save preserves the source and destination if copying fails.
Regression tests cover failures before writing, during writing/cleanup, and at
replacement; existing outputs survive and temporary files are removed.

**Evidence:** [AppPlayback.run_cli](../tuney/app/app_playback.py) unlinks
`self.output` whenever `completed` remains false. That includes failures before a
writer has opened the file. [AudioFileWriter and render_file](../tuney/audio/output_file.py)
also open their destination directly with `mode='w'`.

**Trigger/impact:** Export over an existing file and fail during stream setup,
voice construction, or rendering. The previous file can be deleted or truncated,
even if no replacement was successfully produced. GUI export also writes
directly to the destination.

**Next step:** Write replacement exports to a temporary sibling and replace the
destination only after success. Cleanup must only remove files created by the
current export. Test failure before opening and midway through writing.

### 2. Undo can delete presets unrelated to the action being undone

**Resolved:** Only explicit preset edits capture preset files, and only changed
files enter undo history. Undo/redo verifies expected contents and reports a
conflict rather than overwriting external changes. Writes are staged before
replacement; ordinary text/settings history does no preset I/O. Tests cover
undo/redo isolation, conflicts, and a failure while writing restored files.

**Evidence:** [History.restore](../tuney/ui/history.py) always calls
`restore_user_preset_snapshot`. That function in
[preset.py](../tuney/presets/preset.py) deletes every TOML/JSON file in the preset
directory and then writes the snapshot back.

**Trigger/impact:** Make an ordinary text/settings edit, add or edit a preset
externally, then undo the original edit. Undo removes the new preset or overwrites
the external change. A write failure during restoration leaves a partially
destroyed preset collection.

**Next step:** Limit preset undo to the preset files changed by the corresponding
operation. Preserve unrelated files and avoid deleting the collection first.

### 3. Audio callback performs disk writes, logging, and model construction

**Resolved:** Voice models are prepared at submission. Recording uses a bounded
queue and a writer thread; stopping drains and closes it, propagating failures.
Callback diagnostics and settings persistence are deferred to GUI polling or CLI
cleanup. Tests check thread ownership, sample preservation, writer failure,
overload, and stopping during a write. Hardware latency remains unmeasured.

**Evidence:** [AudioEngine.callback and _drain_commands](../tuney/audio/engine.py)
write recorded blocks synchronously, log status/commands, and call `Mixer.apply`.
[Mixer.apply](../tuney/audio/mixer.py) calls `voice_maker` and constructs
`VoiceState`; [Player.voice_maker](../tuney/audio/player.py) performs tuning
calculations and creates a Pydantic `Voice`. On underflow,
[GlobalConfig.increase_buffer_size](../tuney/app/global_config.py) writes TOML
to disk from that same callback.

**Impact:** Slow storage, expensive tuning, or a burst of commands can exceed the
audio deadline. The underflow response itself adds disk I/O. This contradicts the
callback boundary described in [Maintaining Tuney](../doc/maintaining-tuney.md).
The deadline risk is clear from the call path; its severity needs measurement.

**Next step:** Prepare voices before enqueueing, move persistence and recording
I/O out of the callback, and measure callback duration under realistic load.

### 4. Retriggering a note during its release tail loses the new press

**Resolved:** Only a still-held note rejects a duplicate press. A new press after
release replaces that note's fading voice with a fresh attack. The regression
covers press/release/repress before minimum duration, duplicate held presses,
and the subsequent release, with a one-second WAV fixture.

**Evidence:** [Mixer.apply](../tuney/audio/mixer.py) rejects a press whenever
the note exists in `voices`, even when it has already been removed from
`pressed_notes` and is merely fading out. [Player.start](../tuney/audio/player.py)
accepts the new press because its own pressed-note list no longer contains it.

**Trigger/impact:** Press, release, and quickly press the same note again before
the minimum duration/release tail finishes. The new press is accepted upstream
but discarded by the mixer. A subsequent release does not create the missing
attack. The existing duplicate-press test covers a held note, not this case.

**Next step:** Define retrigger behavior for released voices and test that exact
event sequence, including overlapping characters mapped to the same note.

## P2: behavior and user traps

### 5. Reported buffer growth does not resize the active audio stream

**Resolved:** Deferred underflow handling recreates an existing stream with the
new block size, preserving mixer voices, queued commands, and recording. A batch
of underflows increases the setting once. GUI polling or subsequent playback
submission applies it outside the callback. A fake-stream test verifies actual
block size and uninterrupted synthesized samples across stream replacement.

**Evidence:** [AudioEngine.stream](../tuney/audio/engine.py) reads `buffer_size`
only when constructing the cached stream. Underflow handling changes the Python
field and saves it, but does not replace the active stream.

**Impact:** Logs report a larger buffer while the stream continues with its old
block size. Repeated underflows can keep persisting larger settings without
improving the current session. The test checks the field and log, not the stream.

**Next step:** Schedule any stream reconfiguration outside the callback and
distinguish requested settings from the active stream's actual configuration.

### 6. Recording stop can race with callback writes

**Resolved with issue 3:** The callback retains a local recording reference.
Recording serializes queue submission and stop, then joins the writer before
closing its file. Late submissions are ignored after stop. A test holds a write
in progress while another thread stops, and verifies intact recorded samples.

**Evidence:** [Player.stop_recording](../tuney/audio/player.py) detaches and closes
the writer directly. [AudioEngine.callback](../tuney/audio/engine.py) checks
`self.recorder` and then separately dereferences it to write, with no ownership
handoff protocol.

**Impact:** The UI can clear or close the recorder while the callback is using it.
This can produce an exception or a write against a closed file. This is a
source-level concurrency risk; an interleaving test is needed.

**Next step:** Give one component ownership of writer lifetime and acknowledge
recording stop before closing it.

### 7. Offline rendering allocates an entire gap between events

**Resolved:** Every inter-event interval uses blocks of at most 1,024 frames,
including a shorter final block at each exact event boundary. A WAV regression
checks onset and silence positions and rejects oversized render requests.

**Evidence:** [render_file](../tuney/audio/output_file.py) passes
`frame - rendered` to `Mixer.render` as a single allocation. `BLOCK_SIZE` is used
only for the final release tail.

**Trigger/impact:** An imported performance with a long silent gap or very slow
timing can allocate hundreds of megabytes or more for one interval, with
additional arrays per voice. Export size should not determine peak working
memory this way.

**Next step:** Render every interval in bounded blocks while preserving exact
event-frame boundaries.

### 8. Ordinary audio exports omit speech

**Resolved:** Audio exports and CLI playback include enabled speech. Natural
completion lets speech finish, and GUI loops wait for it before restarting.
Explicit Stop still cancels speech. Tests cover exported speech tails, callback
completion, CLI routing, and replay/loop completion. Speech synthesis is mocked;
WAV fixtures verify the mixing and completion behavior at 48 kHz.

**Evidence:** Speech replay is started in
[KeyRecorder.on_replay](../tuney/app/key_recorder.py). Both GUI Save as Audio
and silent CLI output use [Player.render_file](../tuney/audio/player.py), which
only renders note events through `Mixer`. `use_speech` is not consulted there or
in `AppPlayback.play_cli`. Test-sheet export has its own speech path.

**Impact:** A GUI performance with spoken text exports without that speech;
CLI speech options also do not reach speech playback. This makes identical
configuration produce different results across interfaces.

**Next step:** Define which outputs include speech and either implement parity
or explicitly reject/document unsupported combinations. Test ordinary export,
not only test sheets.

### 9. MIDI-only CLI playback is rejected by the silent-mode guard

**Resolved:** Silent CLI playback accepts enabled MIDI output. A regression
checks MIDI press/release delivery without constructing an audio player.

**Evidence:** [AppPlayback.run_cli](../tuney/app/app_playback.py) rejects
`silent=True` without a file, regardless of MIDI output being enabled.

**Impact:** A user enabling MIDI and explicitly disabling synthesized sound gets
`CLI mode requires sound`, even though MIDI is a valid destination. Meanwhile
MIDI's separate `mute_audio_when_midi_enabled` option offers another muting path.

**Next step:** Validate whether any selected output can consume the performance,
and make the two muting controls' relationship clear.

### 10. Wall-clock changes affect performance timing

**Resolved:** Sequencer uses monotonic time. A deterministic clock test jumps
wall time forward and backward while checking exact event deadlines and waits.

**Evidence:** [Sequencer._run](../tuney/time/sequencer.py) computes elapsed time
with `time.time()`.

**Impact:** A system clock correction can make playback pause unexpectedly or
dispatch many events immediately. Sequencing depends on elapsed time, not the
calendar clock.

**Next step:** Use a monotonic time source for scheduling, with a deterministic
clock-jump test.

### 11. Restored zero loop tempo reaches division by zero

**Evidence:** [LoopState.tempo](../tuney/ui/history.py) is an unconstrained float;
autosave validates against this model. The GUI edit callback rejects nonpositive
values, but [AppPlayback.replay_char_presses](../tuney/app/app_playback.py)
divides event times by restored `loop_tempo`.

**Trigger/impact:** A saved `[loop]` section containing `tempo = 0` passes model
validation and fails when replay is prepared. GUI-only validation does not cover
restoration.

**Next step:** Put the positive, finite tempo requirement on the persisted model
and test autosave recovery from an invalid value.

### 12. Configuration and preset writes are not atomic

**Evidence:** [AppState.save/save_autosave](../tuney/app/app_state.py),
[GlobalConfig.save](../tuney/app/global_config.py), and
[write_preset](../tuney/presets/preset.py) use direct `write_text` replacement.

**Impact:** Interruption or a disk write failure can destroy the previous valid
state. Tolerant autosave parsing cannot recover a file truncated before its data
was written.

**Next step:** Replace individual files atomically after serialization and writing
succeed. Test failure without modifying the last valid file.

### 13. Saving a preset silently overwrites an existing preset

**Evidence:** [preset_name](../tuney/ui/preset_dialogs.py) only asks for a name.
[on_save_preset](../tuney/ui/file_commands.py) immediately writes it without an
overwrite prompt or its own undo checkpoint.

**Impact:** Reusing a name destroys its earlier settings; undo behavior depends
on whatever unrelated checkpoint happened previously.

**Next step:** Make replacement explicit and establish a preset-specific undo
checkpoint before writing.

### 14. Undo cost grows with every recorded event

**Evidence:** [AppPlayback.on_char](../tuney/app/app_playback.py) checkpoints
presses and releases. [History.state](../tuney/ui/history.py) deep-copies the
whole configuration and recorded text and rereads every user preset from disk.
The undo stack has no bound.

**Impact:** Recording N events retains approximately quadratic event history,
plus repeated copies and disk reads of presets. Long sessions can consume large
amounts of memory and stall keyboard handling.

**Next step:** Measure long sessions, group related edits, avoid rereading
unchanged preset files for text operations, and choose a history retention policy.

### 15. Export blocks the GUI until rendering finishes

**Evidence:** [on_save_as_audio/on_save_test_sheet](../tuney/ui/file_commands.py)
perform the complete render synchronously in the menu callback.

**Impact:** Long text or multiple test-sheet presets leave the window
unresponsive with no progress or cancellation. Large allocations in issue 7
compound this.

**Next step:** Provide bounded rendering work with progress and cancellation,
keeping Qt mutations on the GUI thread.

### 16. MIDI callbacks bypass the documented input queue boundary

**Evidence:** [AppMembers.midi_listener](../tuney/app/app_members.py) connects
the MIDI callback directly to `play_note`; [MidiListener.on_message](../tuney/midi/listener.py)
invokes it directly. That reaches mutable `Player` state and stream startup.
The maintenance guide says MIDI callbacks enqueue character presses for Qt.

**Impact:** MIDI input and GUI edits can manipulate playback state from different
threads; MIDI input also bypasses character recording/UI feedback. The exact
hardware-thread interleavings need runtime validation.

**Next step:** Establish the intended MIDI event route and thread ownership,
then align the code and documentation.

### 17. Missing or malformed configuration gets inconsistent CLI errors

**Evidence:** [main](../tuney/app/main.py) catches `ValidationError` and
`FileExistsError`, but [read_file/read_preset](../tuney/presets/preset.py) can
raise `FileNotFoundError`, TOML/JSON parse errors, or plain `ValueError` for an
unknown preset or extension.

**Impact:** Common user input mistakes escape the normal concise error path as
tracebacks. Catching `FileExistsError` does not cover a missing input file.

**Next step:** Handle expected input-file and parse errors consistently without
masking programming errors.

### 18. Local dependency success does not establish release compatibility

**Evidence:** [pyproject.toml](../pyproject.toml) uses editable `../reccy`,
`../ufor`, and `../enge`, while pinning installed Ufor to archive `9fa9d39...`
and leaving Reccy/Enge versions unspecified. The
[release workflow](../.github/workflows/release-builds.yml) sets `UV_NO_SOURCES=1`.
The new help test also needs `reccy.pytest_plugin`.

**Impact:** Local tests exercise a different library set from releases. Recent
sibling API/behavior changes and the plugin may be unavailable in the versions
resolved for packaging. This is a verified dependency divergence, not a claim
that a release build was reproduced failing.

**Next step:** Verify the supported published dependency set in isolation and
declare the minimum/pinned versions actually required. Keep dependency changes
in their own commit.

## P3: documentation, naming, and maintenance

### 19. The consolidated guides contain misleading instructions

**Evidence:** [Using Tuney](../doc/using-tuney.md) shows
`--tuning.root-frequency`; the committed
[help fixture](../test/test_cli_help/test_tuney_help_output.txt) exposes
`--root-frequency`. It describes a platform configuration directory for presets,
but `USER_PRESETS` is always `~/.config/tuney/presets`. It claims File can load a
configuration, whereas the [menu](../tuney/ui/main_menu.py) exposes text opening,
state paste/swap, and saving rather than a configuration-open dialog.

The maintenance guide says NumPy waveform generation remains local, but
[Oscillator](../tuney/audio/oscillator.py) now delegates it to Enge. Its
development setup mentions only the Ufor checkout despite three editable siblings.
The user guide also puts `pipx install tuney` before pipx installation and omits
the old explicit Python-version check for distribution-provided Python.

**Next step:** Correct examples against the help fixture and menus, document
actual paths and sibling setup, and order installation instructions by prerequisites.

### 20. Copying text records timing metadata that pasting ignores

**Evidence:** [on_copy_text](../tuney/ui/file_commands.py) writes a custom
`application/x-tuney-char-presses+json` payload. `on_paste_text` reads only plain
text and generates fresh timings; no other consumer reads that MIME type.

**Impact:** Copy/paste within Tuney loses recorded timing even though the copy
implementation appears designed to preserve it.

**Next step:** Decide whether timing-preserving paste is intended; implement and
test it or remove the unused payload and explain timing regeneration.

### 21. Large modules concentrate unrelated responsibilities

**Measured:** [control_panel.py](../tuney/ui/control_panel.py) has 1,432 lines,
[main_window.py](../tuney/ui/main_window.py) 659, and
[layout.py](../tuney/ui/layout.py) 604. Control-panel code combines generic widget
construction, value parsing, model mutation, cache invalidation, MIDI lifecycle,
and scale-error presentation despite existing helper modules.

[test_tuney.py](../test/test_tuney.py) has 2,720 lines,
[test_control_panel.py](../test/test_control_panel.py) 1,740, and
[_test_app_keys.py](../test/_test_app_keys.py) 1,130.

**Next step:** Split only along demonstrated ownership boundaries when working
on those areas. Avoid arbitrary line-count limits or a broad refactor merely to
shorten files. Directory inventory found 29 direct tracked files in `tuney/ui`
and 33 in `test`; those counts alone do not justify additional nesting.

### 22. Qt tests are hidden inside one subprocess test

**Evidence:** [test_app_keys.py](../test/test_app_keys.py) runs 17 named checks
through a hard-coded subprocess script, all reported as `test_app_keys`.
`subprocess.run` captures output and has no timeout.

**Impact:** Individual checks cannot be selected normally with pytest; the first
failure prevents later checks from running, and a hung child can hang the suite.
Captured child details are not deliberately presented on failure.

**Next step:** Preserve process isolation but expose individually selectable
cases, report child diagnostics, and bound subprocess execution time.

### 23. Obsolete waveform code and a test-only production wrapper remain

**Evidence:** [audio/scipy.py](../tuney/audio/scipy.py) still contains copied
waveform implementations, but a repository Python-reference search found no
consumer after Enge adoption. [OfflineRenderer](../tuney/audio/renderer.py) is
only used by `test_audio_renderer.py`; production file rendering uses
`output_file.render_file` directly.

**Impact:** The apparent rendering entry points make ownership unclear and can
lead maintainers to fix or test a path the application does not use.

**Next step:** Verify there are no supported external consumers, remove obsolete
waveforms, and test the production rendering path directly or make the wrapper
an explicitly test-local helper.

### 24. Ambiguous names obscure units, roles, and destinations

**Evidence:** `TextTimings.timings_` means effective durations, distinct from
`timings`; `AppMembers` gives little indication that it constructs runtime
services; tuning's generic enum `Type` obscures what is selected. `Scale`'s
docstring still says `N-just limit`, although `Computed.limit` is a maximum
rational denominator. `MidiOut.channel='omni'` means default output channel,
whereas MIDI input uses the same word for all channels. `output` is described as
an audio file although MIDI extensions select another format, and `silent`
selects offline synthesis when a file is requested rather than suppressing it.

**Next step:** Clarify help and labels first. Consider focused internal names
such as effective timings and tuning source; treat public option renames as
separate interface decisions, not cosmetic cleanup.

## Suggested order

Address output and preset data safety first, then callback ownership and note
retriggering. Resolve dependency/release divergence before packaging. Follow with
timing/export behavior and documentation corrections. Organize large modules
only as needed for those fixes.

Additional work beyond the prompt: None.
