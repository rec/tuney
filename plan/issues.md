# tuney issues

Reviewed on 2026-09-29 at commit `becadd8`. This is a source review of the production code, tests, configuration, documentation, and release workflow, with local reccy source checked for reusable facilities. No application or hardware was run for that review. Findings labelled **risk** describe plausible failure paths that need a reproducer; the others follow directly from the current code. P1 means potential data loss, unbounded resource use, or an important runtime failure; P2 means a behavioral or usability defect; P3 means maintainability or coverage debt. Issue numbers remain stable as completed findings are removed.

## P1: data and runtime safety

## P2: behavior and user-facing traps

## P3: structure, reuse, and verification

### 25. Two tiny single-use modules add indirection

[tuney/error.py](../tuney/error.py) defines `TuneyError` but has no references in the repository. [tuney/ui/platform.py](../tuney/ui/platform.py) contains one five-line `command_key` helper used only by layout. Remove the unused error type and consider placing the helper at its sole call site during nearby work. Other small modules such as time units and UI constants have multiple consumers and are serving a useful shared role.

### 27. Failure-path tests miss the most consequential interleavings

The test suite has substantial CLI, GUI, MIDI, and WAV regression coverage, but does not exercise sparse long speech or GUI queue saturation. Add focused tests at the relevant boundaries before changing those paths. These are coverage gaps, not evidence that each risk is currently reproduced.

### 28. Some test files overlap and packaged behavior remains unverified

Audio renderer and voice-envelope tests both cover envelope, binaural, and phase behavior at different layers; control-panel and layout tests also overlap in widget assertions. Review duplicated assertions when editing those files, while preserving their distinct integration coverage. The release workflow runs headless tests and builds packages, but does not launch a packaged GUI or validate physical audio, MIDI, or global keyboard input ([.github/workflows/release-builds.yml](../.github/workflows/release-builds.yml)). Keep those as explicit release checks rather than treating CI success as hardware validation.

The large [control-panel tests](../test/test_control_panel.py), [audio renderer tests](../test/test_audio_renderer.py), and [GUI event tests](../test/_test_app_keys.py) also have navigation costs. Split them by existing test ownership boundaries when changing them, without duplicating fixtures or coverage.

### 29. Small naming and documentation inaccuracies remain

The `Tuney` model docstring says “tuny” ([tuney/config/tuney.py](../tuney/config/tuney.py), line 27). Generic `Tuning.type` gives little hint of its available sources or fallback behavior. Correct the typo and document the chosen source semantics when addressing finding 20.

## Scope and suggested order

Start with direct data-loss and wrong-output paths (13, 16, 17, 20), then address concurrent paths (8, 9, 11, 18), followed by UI/API clarity and maintenance findings. The risks marked above need focused reproduction or failure injection before choosing an implementation.

Tuney has no production HTTP or socket request path in this review, so there is no runtime network-retry mechanism to assess. Its relevant intermittent external interfaces are MIDI/audio devices, speech input, and the filesystem, including removable or full volumes. Dependency downloads and Git operations in development and CI are separate from user-facing runtime behavior.

## Additional work beyond the prompt

None.
