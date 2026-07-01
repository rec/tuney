# Dear PyGui Port Plan

This plan assumes "Dear GUI" means Dear PyGui, the Python GUI toolkit built on
Dear ImGui. Dear PyGui is documented as a GPU-accelerated, cross-platform GUI
toolkit for Python with buttons, radio buttons, menus, layout tools, tables,
drawings, themes, tooltips, menu bars, file selectors, and a render loop.

Sources:

* https://dearpygui.readthedocs.io/en/latest/
* https://dearpygui.readthedocs.io/en/latest/documentation/render-loop.html
* https://dearpygui.readthedocs.io/en/latest/documentation/item-callbacks.html

## Goals

Port the current `customtkinter` GUI to Dear PyGui without changing Tuney's
model, CLI behavior, audio engine, MIDI output, serialization, or keyboard
listener semantics.

The port should preserve these user-visible workflows:

* Live note buttons that mirror keystroke state and can also generate
  `CharPress` events.
* Text display and character count updates during recording and replay.
* Replay, record, stop, save, and clear transport controls.
* File menu commands for save, clear, and refresh devices.
* Control panel editing for all visible `Tuney` configuration fields.
* Device and MIDI output refresh controls.
* Hover help controlled by `Tuney.hover_time`.
* Correct focus behavior, including ignoring new keystrokes while focus is in
  the control panel.

## Non-Goals

Do not redesign the model or audio code during the port. Do not change config
file shape, command-line flags, snapshot formats, mapper semantics, scale
semantics, playback timing, or MIDI behavior.

Do not keep two complete GUI implementations indefinitely. A short-lived
parallel implementation is acceptable only during the transition, behind one
small switch, and should be removed once the Dear PyGui path is complete.

## Current Tk Responsibilities

The current UI is spread across these modules:

* `tuney/ui/app.py`: top-level app lifecycle, menus, accelerators, focus state,
  save dialogs, replay state, audio error polling, and queued keyboard events.
* `tuney/ui/layout.py`: top-level layout, text box, note grid, replay button,
  transport strip, control panel, and device refresh.
* `tuney/ui/control_panel.py`: dynamic controls from Pydantic models,
  validation, option refresh, note-grid rebuilds, disabled MIDI controls, and
  hover text.
* `tuney/ui/note_button.py`: note button pressed/released state and click
  toggling.
* `tuney/ui/transport.py`: transport buttons, icons, flash timer, state
  machine, and hover text.
* `tuney/ui/tooltip.py`: delayed hover help.

The port should move these responsibilities, not duplicate or reinterpret
them.

## Proposed Shape

Create a small Dear PyGui backend under `tuney/ui/dpg/` while keeping model
ownership in `Tuney`.

Suggested modules:

* `tuney/ui/dpg/app.py`: viewport setup, render loop, menu bar, file dialogs,
  keyboard queue polling, focus state, and shutdown.
* `tuney/ui/dpg/layout.py`: main window layout, text display, control panel,
  transport row, replay button, and note grid rebuilds.
* `tuney/ui/dpg/control_panel.py`: Pydantic model controls rendered with Dear
  PyGui widgets.
* `tuney/ui/dpg/note_button.py`: note button state, labels, and callbacks.
* `tuney/ui/dpg/transport.py`: transport controls, state updates, icons or text
  fallback, and record flashing.
* `tuney/ui/dpg/tags.py`: tag helpers for stable widget identifiers.

Keep the public app contract close to the current `App`:

* `start()`
* `destroy()` or equivalent shutdown method
* `on_char(CharPress)`
* `on_clear()`
* `on_save()`
* `on_refresh_devices()`
* `on_replay()`
* `on_transport_state(...)`
* `is_replaying`
* `is_saving`
* `has_focus`
* `focus_in_control_panel`

This keeps `Tuney` changes small.

## Phase 1: Dependency and Spike

Add `dearpygui` in a separate dependency commit, as required by the project
rules for `uv` changes.

Then build a throwaway spike outside runtime code or behind an explicit private
entry point that proves:

* The viewport opens and closes cleanly on macOS.
* The render loop can poll `Tuney` keyboard events without blocking audio.
* Menu items and accelerator-equivalent handlers can call the current app
  callbacks.
* Dear PyGui file dialogs can save TOML, JSON, and WAV paths.
* Tooltips can be delayed according to `hover_time`, or a small timer wrapper is
  needed.
* Focus state can distinguish control-panel input from global note input.

Delete the spike before the real implementation lands.

## Phase 2: App Shell

Implement the Dear PyGui app shell with no dynamic control panel yet.

Include:

* Viewport title `Tuney`.
* App icon if Dear PyGui supports the existing PNG path on macOS; otherwise
  document that packaging is needed for true app identity.
* File menu commands for Save, Clear, and Refresh Devices.
* A render-loop callback or frame polling function that replaces Tk `after`.
* Audio diagnostic polling equivalent to the current queue poll.
* A shutdown path that calls `tuney.player.close()`.

Acceptance tests should stay unit-level. Do not launch the GUI in pytest.
Extract pure callback/state helpers where tests need coverage.

## Phase 3: Transport and Replay

Port the transport controls and replay button.

Keep the existing state machine behavior:

* Record toggles between ready/recording/paused.
* Stop returns to ready and saves through the existing recording path.
* Save performs the save action currently assigned to the transport save button.
* Clear clears the current recording.
* The record indicator flashes while recording.
* Hover tips appear for all transport controls.

Use simple text or Dear PyGui drawing primitives first. Preserve the current
icons only after behavior is stable.

## Phase 4: Note Grid and Text Display

Port the note grid and text display.

Requirements:

* Grid dimensions still come from `tuney.note_labels`.
* Note labels use the same `NoteLabel.text`.
* Button pressed/released state changes on keyboard events.
* Clicking a note button toggles it and sends `CharPress` to `Tuney`.
* Rebuilding the note grid clears cached `tuney.note_labels`.
* Replay updates both button states and the text display.
* Text display remains read-only to normal typing.

This phase should preserve the current separation where `Tuney` owns recording,
playback, and mapping behavior.

## Phase 5: Control Panel

Port the dynamic control panel after the shell, transport, and note grid are
working.

Map current control types directly:

* `bool`: checkbox.
* enum: radio buttons.
* known option providers: combo box.
* int/float/string/list-like fields: text input with existing parsing rules.
* disabled MIDI fields: disabled or visibly dimmed widgets when MIDI is off.
* field hover text: same `_field_help` and rewrap behavior.

Preserve current special cases:

* Hidden fields from `CONTROL_CONFIGS`.
* General fields at the top.
* Compact row layouts from `CONTROL_CONFIGS`.
* Device and MIDI output refresh.
* Mapper and Scale edits refresh the note grid.
* `Scale.intervals` edits as compact interval text.
* Invalid scale edits mark the relevant input without crashing.

The best way to keep this maintainable is to split UI-independent control
metadata from widget construction. The existing row selection, visible-field
selection, and parsing helpers can be reused or moved into a neutral helper
module before replacing the widgets.

## Phase 6: Replace the Runtime Entry

Once Dear PyGui reaches feature parity, switch `Tuney.app` to construct the new
app.

Keep the old Tk implementation available only long enough to compare behavior
manually. Remove it, remove `customtkinter`, and update dependency files in a
separate `uv` commit after the Dear PyGui path is verified.

## Phase 7: Verification

Before removing Tk:

* Run `pytest`.
* Run `ruff check --fix --select B,E,F,I tuney test*`.
* Run `ty check tuney`.
* Manually verify live typing, note-button clicking, replay, recording, save,
  clear, file save, refresh devices, hover help, MIDI enable/disable visuals,
  and control-panel focus behavior.
* Manually verify macOS behavior, especially app name, file dialogs, focus
  transitions, and keyboard listener shutdown.

After removing Tk:

* Repeat the full verification.
* Remove obsolete tests that only cover Tk-specific implementation details.
* Keep tests for model parsing, control metadata, transport state, and app
  callback behavior.

## Risks

Dear PyGui is not a Tk drop-in replacement. The risky areas are focus handling,
native file-dialog behavior, keyboard accelerator behavior, and matching the
current dynamic control-panel layout closely enough to remain usable.

The audio engine should stay isolated from the UI thread. If the Dear PyGui
render loop encourages polling in a different shape, keep that change inside
the app shell rather than pushing UI concerns into `Tuney` or the audio
modules.

## Additional Work Beyond The Prompt

None.
