# Split `control_panel.py`

## Goal

Make `tuney/ui/control_panel.py` easier to understand without changing the
generated control panel's behavior. The split should separate model inspection,
layout planning, widget construction, and model mutation, while keeping the
public entry point as `ControlPanel`.

Additional work beyond the prompt

None.

## Current Problem

`control_panel.py` is doing several jobs at once:

- Building and caching beginner and advanced pages.
- Deciding which model fields are visible.
- Reading `Annotated` metadata such as `Display`, `Numeric`, `Options`,
  `Beginner`, `General`, and `Hidden`.
- Grouping fields into rows and collapsible sections.
- Creating Qt widgets.
- Parsing text entered by users.
- Validating and writing values back into Pydantic models.
- Synchronizing duplicate widgets across beginner and advanced pages.
- Managing special cases for tuning, scale notes, MIDI enable state, and note
  grid rebuilds.

These are coherent responsibilities, but keeping them in one 1200-line file
makes unrelated changes risky.

## Proposed Modules

### `tuney/ui/control_panel.py`

Keep only the public widget and high-level orchestration:

- `ControlPanel`
- `_OptionControl`
- page caching and `show_mode`
- `rebuild_control_panel`
- `_rebuild_parent_control_panel`

This file should import helpers from the new modules and remain the main API for
other UI code.

### `tuney/ui/control_metadata.py`

Move metadata and visibility helpers:

- `_visible_field_names`
- `_visible_control_names`
- `_visible_child_names`
- `_visible_tuning_control_names`
- `_has_visible_fields`
- `_active_tuning_type`
- `_is_beginner_field`
- `_model_tree`
- `_control_metadata`
- `_numeric_metadata`
- `_options_metadata`
- `_has_metadata`
- `_is_suppressed_field`

This module should have no Qt imports.

### `tuney/ui/control_layout.py`

Move row and section planning:

- `INLINE_CHILDREN`
- `GENERAL_COLUMNS`
- `_general_controls`
- `_control_groups`
- `_control_refs`
- `_control_ref_rows`
- `_control_rows`
- `_grid_rows`

This module should return data structures, not widgets. It may depend on
`control_metadata.py`, but should avoid direct Qt widget construction.

### `tuney/ui/control_widgets.py`

Move Qt widget construction:

- `SECTION_STYLE`
- `_section`
- `_add_collapsible_section`
- `_set_section_expanded`
- `_add_control_group_grid`
- `_add_control_grid`
- `_add_control_cell`
- `_add_labeled_control_frame`
- `_configure_label`
- `_configure_editor`
- `_is_wide_field`
- `_add_control`
- `_add_option_control`
- `_add_bool_control`
- `_add_entry_control`
- `_add_spin_control`
- `_add_enum_control`
- `_set_widget_state`
- `_parent_layout`

This should be the only large module with broad Qt widget imports.

### `tuney/ui/control_binding.py`

Move model writes and widget synchronization:

- `CONTROL_BINDINGS`
- `INVALID_SCALE_WIDGET_TEXT_COLORS`
- `_bind_control`
- `_sync_model_controls`
- `_set_model_value`
- `_checkpoint_undo`
- `_clear_cached_values`
- `_set_mapping_entry_state`
- `_set_invalid_scale_widget`
- `_clear_invalid_scale_widgets`
- `_set_midi_controls_state`
- `_rebuild_note_grid_if_mapping_changed`
- `_rebuild_note_grid`
- `_after`

This module will still need Qt imports, but its purpose is state synchronization
rather than widget construction.

### `tuney/ui/control_parsing.py`

Move type and string conversion helpers:

- `_parse_entry_value`
- `_tuning_expression_text`
- `_entry_text`
- `_entry_width`
- `_annotation_types`
- `_expects_json`
- `_enum_class`
- `_flatten_type_args`
- `_can_use_spin_control`
- `_is_int_annotation`

This module should be mostly independent of Qt. `_entry_width` may continue to
consume `Display` and `Numeric` metadata.

### `tuney/ui/control_tooltips.py`

Move tooltip helpers:

- `_add_field_tooltips`
- `_field_widgets`
- `_field_hover_text`
- `_rewrap_hover_text`
- `_field_help`

This module can depend on Qt and `Tooltip`, but not on model mutation.

### `tuney/ui/tuning_controls.py`

Move tuning-specific panel behavior:

- `_add_tuning_controls`
- `_set_tuning_type_form`
- `_set_tuning_form`

This isolates the `QStackedWidget` tuning special case from general form
construction.

## Suggested Order

1. Extract `control_metadata.py`.

   This is the safest first step because it can be tested through existing
   visibility and beginner-mode regressions without changing Qt widget behavior.

2. Extract `control_parsing.py`.

   The parsing helpers already have focused unit tests. Move them before moving
   widget code so text-entry behavior remains easy to verify.

3. Extract `control_layout.py`.

   Move only the pure planning functions first. Keep widget creation in
   `control_panel.py` until the layout tests pass.

4. Extract `control_tooltips.py`.

   This removes the tyro help lookup and tooltip traversal from the main file.
   Existing tooltip tests should cover the move.

5. Extract `control_binding.py`.

   Move model mutation and sync in one step because these functions are tightly
   coupled by `CONTROL_BINDINGS`.

6. Extract `tuning_controls.py`.

   Move the tuning stack behavior after binding has been separated, because
   tuning controls call both widget construction and model mutation paths.

7. Extract `control_widgets.py`.

   Move widget construction last. This is the broadest change because it touches
   most Qt imports and helper call sites.

8. Leave a small `control_panel.py`.

   After the extractions, `control_panel.py` should mostly read as:

   - construct the scroll area
   - manage cached pages
   - call section/layout/widget builders
   - expose refresh/rebuild entry points

## Testing After Each Step

Run focused tests after every extraction:

- `uv run pytest test/test_control_panel.py`
- `uv run pytest test/test_tooltip.py`
- `uv run pytest test/test_app_keys.py`

Run full verification before committing each meaningful extraction:

- `uv run pytest`
- `uv run ruff check --fix --select B,E,F,I tuney install test/*.py`
- `uv run ruff format`
- `uv run ty check tuney`
- pyupgrade sweep
- `git diff --check`

## Constraints

- Do not change visible behavior during the split.
- Do not introduce a second control-panel implementation.
- Keep `ControlPanel` as the imported widget used by `Layout`.
- Do not move field metadata classes out of `tuney/cfg/display.py`.
- Prefer small commits that each leave tests passing.
