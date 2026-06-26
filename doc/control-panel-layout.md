# Control Panel and Transport Layout Plan

## Goal

Make the control panel, Transport strip, and Replay panel denser and easier to
scan without changing the model, command line, audio behavior, keyboard
handling, or saved configuration shape.

Additional work beyond the prompt

None.

## Current Problems

The control panel still behaves like a generated form. It exposes the right
fields, but many labels and controls consume more horizontal and vertical space
than their values require. The Transport and Replay areas are also visually
separate from the rest of the tool surface, so they do not make the best use of
the available width.

The result is that simple settings, such as booleans, small integers, and small
floats, take as much room as more complex settings. This makes the advanced
sections feel larger than they are.

## Layout Reorganization

Use the existing control metadata as the source of truth, but add a second layer
that describes presentation density:

* `primary`: fields needed during normal playing and recording.
* `advanced`: fields useful for detailed tuning or uncommon setup.
* `wide`: text-like fields that need a full row.
* `compact`: booleans, enums, small integers, and short floats.

Keep the generated-control approach, but make each row a deliberate composition:

* Put related compact fields on the same row.
* Give string fields and list-like fields their own row only when they need it.
* Keep section headings minimal and avoid repeated parent names in labels.
* Use each field's visible label as the shortest unambiguous local name.

For example, in a section already titled `MIDI`, labels should be `enable`,
`output`, `channel`, `velocity`, and `note offset`, not labels that repeat
`MIDI`.

## Beginner and Advanced Modes

Add a mode switch at the top of the control panel:

* Beginner mode shows the top-level workflow controls and the safest musical
  controls.
* Advanced mode shows every visible field.

Beginner mode should not be a second model or a second set of controls. It
should be a filter over the same control metadata, so changing modes preserves
the current values and uses the same validation path.

Suggested beginner fields:

* top-level text, recording, and output settings that are relevant in the GUI.
* mapper alphabet, accidentals, limiter, and range limit.
* player gain, note offset, waveform, and basic oscillator shape.
* scale root, tuning type, and interval text.
* MIDI enable and output.
* device output and sample rate.

Advanced mode should include the remaining visible fields, including timing,
polyphony, keyboard behavior, hover timing, and detailed tuning parameters.

## Label and Whitespace Rules

Labels should be local to the current section and should avoid unnecessary
prefixes. Use consistent casing and spacing:

* Use short words: `rate`, `dtype`, `gain`, `root`, `begin`, `end`.
* Use two words only where one word is ambiguous: `note offset`, `range limit`.
* Keep checkbox and radio labels beside the indicator, not above it.
* Keep enum groups tightly packed by setting explicit spacing on their layout.
* Give compact controls fixed widths based on expected value length.

The control panel should not rely on stretch space inside individual field
containers. If a field needs empty space, it should come from the row layout, not
from the control cell itself.

## Better Number Controls

Qt already gives us the useful pieces through PySide6:

* `QSpinBox` for integers.
* `QDoubleSpinBox` for floats.
* `QSlider` for bounded linear values.
* `QDial` for compact knob-style adjustment.

Qt does not provide a standard single widget that combines a numeric text box
and a dial. The normal Qt pattern is a small composite widget that contains a
`QDoubleSpinBox` or `QSpinBox` plus a `QDial` or `QSlider`, with both connected
to the same value.

That is probably better than adding a new dependency. PySide6 is already in the
project, and a small composite widget can share the same parsing and validation
path as the existing fields. A dependency should only be considered if it gives
substantially better controls without taking over styling, layout, or event
handling.

Suggested widgets:

* Use spin boxes for all bounded integers and floats.
* Add a dial only for values where analog adjustment feels natural, such as
  gain, oscillator duty cycle, oscillator period, and loop trimming.
* Use a horizontal slider instead of a dial when the value has a clear low to
  high direction.
* Keep direct text entry available for exact values.

## Transport and Replay Panel

Treat Transport and Replay as one control band instead of separate visual
islands.

Suggested layout:

* Put record, stop, clear, and save in a single fixed-height row.
* Keep Replay in the same band, visually separated by spacing rather than a
  nested panel.
* Use icon buttons with tooltips and stable square hit targets.
* Keep the replay button larger than the transport icon buttons only if it
  remains the dominant action in the current workflow.
* Align the button baselines and centers so the band reads as one unit.

The record flashing state should change only color or outline, not geometry.
Replay state should change text or icon state without moving the button.

## Implementation Phases

1. Extract presentation metadata from the existing control panel into a small
   layout policy table. Do not change widgets yet.
2. Add Beginner and Advanced filtering over that metadata.
3. Replace numeric text boxes with `QSpinBox` and `QDoubleSpinBox` where the
   field has a known numeric type.
4. Add an internal spin-box-plus-dial composite for a small set of natural dial
   fields.
5. Tighten checkbox, radio, and compact field row spacing.
6. Rework the Transport and Replay area into one fixed-height control band.
7. Re-run focused GUI unit tests and update only behavior-based tests that are
   affected by widget type changes.

## Risks

The main risk is turning a generated control panel into a hand-built UI by
accident. The implementation should keep one metadata path and one validation
path. Beginner mode, compact layout, and richer numeric controls should all be
presentation choices over the same model fields.

The second risk is overusing dials. Dials are attractive, but they are weak for
precise values unless paired with numeric entry. Use them sparingly.
