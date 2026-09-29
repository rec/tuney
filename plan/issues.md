# tuney issues

Reviewed on 2026-09-29 at commit `becadd8`. This is a source review of the production code, tests, configuration, documentation, and release workflow, with local reccy source checked for reusable facilities. No application or hardware was run for that review. Findings labelled **risk** describe plausible failure paths that need a reproducer; the others follow directly from the current code. P1 means potential data loss, unbounded resource use, or an important runtime failure; P2 means a behavioral or usability defect; P3 means maintainability or coverage debt. Issue numbers remain stable as completed findings are removed.

## P1: data and runtime safety

## P2: behavior and user-facing traps

## P3: structure, reuse, and verification

### 29. Small naming and documentation inaccuracies remain

The `Tuney` model docstring says “tuny” ([tuney/config/tuney.py](../tuney/config/tuney.py), line 27). Generic `Tuning.type` gives little hint of its available sources or fallback behavior. Correct the typo and document the chosen source semantics when addressing finding 20.

## Scope and suggested order

Start with direct data-loss and wrong-output paths (13, 16, 17, 20), then address concurrent paths (8, 9, 11, 18), followed by UI/API clarity and maintenance findings. The risks marked above need focused reproduction or failure injection before choosing an implementation.

Tuney has no production HTTP or socket request path in this review, so there is no runtime network-retry mechanism to assess. Its relevant intermittent external interfaces are MIDI/audio devices, speech input, and the filesystem, including removable or full volumes. Dependency downloads and Git operations in development and CI are separate from user-facing runtime behavior.

## Additional work beyond the prompt

None.
