# tuney issues

Reviewed on 2026-09-29 at commit `becadd8`. This is a source review of the production code, tests, configuration, documentation, and release workflow, with local reccy source checked for reusable facilities. No application or hardware was run for that review. Findings labelled **risk** describe plausible failure paths that need a reproducer; the others follow directly from the current code. P1 means potential data loss, unbounded resource use, or an important runtime failure; P2 means a behavioral or usability defect; P3 means maintainability or coverage debt. Issue numbers remain stable as completed findings are removed.

## P1: data and runtime safety

## P2: behavior and user-facing traps

### 20. Requested tuning source can silently change

`Tuning.active` falls back to another populated source, or a fresh computed tuning, if the selected `type` has no value ([tuney/scale/tuning.py](../tuney/scale/tuning.py), lines 110-115). A configuration requesting a table can therefore play a different tuning without an error. Either reject the incomplete selection at load or make the fallback an explicit user choice.

### 21. MIDI input open failures leave an apparently enabled listener

`MidiListener.start` logs an input-open failure and returns ([tuney/midi/listener.py](../tuney/midi/listener.py), lines 23-29). The enabled setting remains true and the device monitor does not retry that listener. Show a failed state or retry on a real device change, with a test for an input that appears after initial failure.

### 22. Configuration labels have different meanings across flows

`silent` controls live playback behavior while offline export still renders audio; “omni” means all channels for input but channel 1 for output. These distinctions are present in code but easy to misread in configuration and UI. Rename the labels or add concise help at the control where users choose them. Keep the underlying MIDI channel semantics explicit in tests.

### 23. Close errors use the wrong action in their message

`MidiOut.close` logs “Could not open MIDI output” for a close failure ([tuney/midi/midi.py](../tuney/midi/midi.py), lines 142-146). Report “close” and include the selected port, so troubleshooting points at the actual operation.

## P3: structure, reuse, and verification

### 24. Large UI classes concentrate unrelated responsibilities

[tuney/ui/control_panel.py](../tuney/ui/control_panel.py) is about 1,331 lines and [tuney/ui/main_window.py](../tuney/ui/main_window.py) about 665. They combine widget construction, signal wiring, state mutation, device lifecycle, and persistence, making shutdown and state-transition changes hard to review. Split by an existing responsibility boundary when modifying those paths; avoid a speculative rewrite. The biggest tests, [test/test_control_panel.py](../test/test_control_panel.py) (about 1,753 lines), [test/test_audio_renderer.py](../test/test_audio_renderer.py) (about 1,210), and [test/_test_app_keys.py](../test/_test_app_keys.py) (about 1,189), have similar navigation costs.

### 25. Two tiny single-use modules add indirection

[tuney/error.py](../tuney/error.py) defines `TuneyError` but has no references in the repository. [tuney/ui/platform.py](../tuney/ui/platform.py) contains one five-line `command_key` helper used only by layout. Remove the unused error type and consider placing the helper at its sole call site during nearby work. Other small modules such as time units and UI constants have multiple consumers and are serving a useful shared role.

### 27. Failure-path tests miss the most consequential interleavings

The test suite has substantial CLI, GUI, MIDI, and WAV regression coverage, but does not exercise sparse long speech or GUI queue saturation. Add focused tests at the relevant boundaries before changing those paths. These are coverage gaps, not evidence that each risk is currently reproduced.

### 28. Some test files overlap and packaged behavior remains unverified

Audio renderer and voice-envelope tests both cover envelope, binaural, and phase behavior at different layers; control-panel and layout tests also overlap in widget assertions. Review duplicated assertions when editing those files, while preserving their distinct integration coverage. The release workflow runs headless tests and builds packages, but does not launch a packaged GUI or validate physical audio, MIDI, or global keyboard input ([.github/workflows/release-builds.yml](../.github/workflows/release-builds.yml)). Keep those as explicit release checks rather than treating CI success as hardware validation.

### 29. Small naming and documentation inaccuracies remain

The `Tuney` model docstring says “tuny” ([tuney/config/tuney.py](../tuney/config/tuney.py), line 27). Generic `Tuning.type` gives little hint of its available sources or fallback behavior. Correct the typo and document the chosen source semantics when addressing finding 20.

## Scope and suggested order

Start with direct data-loss and wrong-output paths (13, 16, 17, 20), then address concurrent paths (8, 9, 11, 18), followed by UI/API clarity and maintenance findings. The risks marked above need focused reproduction or failure injection before choosing an implementation.

Tuney has no production HTTP or socket request path in this review, so there is no runtime network-retry mechanism to assess. Its relevant intermittent external interfaces are MIDI/audio devices, speech input, and the filesystem, including removable or full volumes. Dependency downloads and Git operations in development and CI are separate from user-facing runtime behavior.

## Additional work beyond the prompt

None.
