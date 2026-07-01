# Better Audio Plan

## Goals

- Play all synthesized notes through one long-lived audio output stream.
- Keep note starts and stops responsive during live typing and replay.
- Avoid clicks at note boundaries and clipping when several notes overlap.
- Recover predictably when the selected device or its configuration changes.
- Make audio behavior testable without opening a physical audio device.

MIDI output is independent of this work. The existing oscillator, scale, and device
models should remain the configuration surface unless a phase below requires a
specific change.

## Current Problems

`MultiPlayer` starts an `OscillatorPlayer` thread and a `sounddevice.OutputStream`
for every active note. This makes timing and mixing depend on the host audio stack,
creates unnecessary threads and streams, and provides no shared place to limit the
combined signal. Note state is also split between `MultiPlayer`, `Runner`, and each
`Player`, which makes shutdown and device changes harder to coordinate.

The waveform generator is useful independently, but playback lifecycle,
synthesis, envelopes, and device I/O are coupled closely enough that callback
behavior is difficult to test in isolation.

## Phase 1: Define and Measure Behavior

1. Add focused tests for oscillator phase continuity, attack and release envelopes,
   overlapping notes, repeated note-on events, and stop-all behavior.
2. Add an offline renderer that accepts note events and produces NumPy blocks using
   the same mixing code intended for the device callback.
3. Record callback status and stream failures in a small diagnostic interface so
   underruns and device errors are visible without printing from the real-time
   callback.

Acceptance criteria:

- Audio logic can be exercised without constructing `sounddevice.OutputStream`.
- Tests define the expected behavior for duplicate presses and unmatched releases.
- A callback block performs no logging, stream construction, or thread creation.

## Phase 2: Introduce Voices and a Mixer

1. Represent each active note as a voice containing oscillator phase, frequency,
   gain, and envelope state.
2. Move attack and release handling from `OscillatorPlayer` into the voice so a
   released note remains active until its release envelope reaches zero.
3. Add a mixer that renders every active voice into one output block, sums the
   results, removes completed voices, and applies the master gain once.
4. Preserve oscillator phase between blocks instead of deriving it from independent
   stream frame counters.

Acceptance criteria:

- Rendering the same event sequence with different block sizes produces equivalent
  output within a numerical tolerance.
- Starting or releasing one note does not reset or interrupt another note.
- No discontinuity is introduced at block boundaries.

## Phase 3: Use One Output Stream

1. Replace per-note `Runner` and `OscillatorPlayer` instances with one audio engine
   owned by `MultiPlayer`.
2. Open one `sounddevice.OutputStream` when audio starts, render mixer blocks in its
   callback, and close it during application shutdown.
3. Send note-on, note-off, stop-all, and configuration commands to the engine through
   a thread-safe queue. Drain commands at the start of each callback.
4. Keep locks, allocation, validation, and model reconstruction out of the callback
   path where practical.

Acceptance criteria:

- Polyphony uses exactly one output stream and no thread per note.
- Note commands are applied no later than the next audio block.
- Stop-all releases or silences every voice and leaves no playback thread running.

## Phase 4: Levels and Sound Quality

1. Choose an explicit polyphonic gain policy. Start with conservative headroom and
   add a limiter only if measured overlap still clips.
2. Make attack and release durations time-based and convert them to samples using the
   active stream sample rate.
3. Replace non-band-limited waveforms for higher notes if aliasing is audible. Keep
   the current waveform names and compare any replacement against offline renders.
4. Verify mono and configured multi-channel output, with an explicit channel mapping
   instead of relying on NumPy broadcasting.

Acceptance criteria:

- The mixed signal remains within the configured output range for the documented
  maximum polyphony.
- Envelope duration is stable across sample rates and block sizes.
- Waveform changes are backed by spectral or render-based regression tests.

## Phase 5: Device Lifecycle

1. Resolve the selected device and effective sample rate before creating voices.
2. On a device configuration change, stop the existing stream, clear or release its
   voices, and start a new stream with the new settings.
3. Surface stream startup and callback failures to the GUI without performing GUI
   operations from the audio callback.
4. Make application shutdown close the stream deterministically.

Acceptance criteria:

- Refreshing or changing devices does not leave an old stream active.
- A failed device open leaves the engine stopped and reports one actionable error.
- Repeated start and stop cycles do not leak threads or streams.

## Implementation Order

Implement Phases 1 through 3 as one architectural sequence, with each commit passing
offline tests. Phase 4 should follow only after the single-stream mixer is stable.
Device lifecycle work can then use that single ownership boundary instead of adding
recovery logic to the current per-note streams.

Do not retain the current per-note playback path as a fallback. Once the new engine
meets the Phase 3 acceptance criteria, remove `OscillatorPlayer`, `Runner`, and other
concurrency code that no longer has a caller.
