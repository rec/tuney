# Layout Annotations Plan

Replace `ControlConfig` with field-level annotations on the data classes that own the fields.

## Goal

Move the control-panel layout metadata out of `tuney/ui/constants.py` and into the model field definitions. The control panel should read layout intent from the same fields it renders, instead of maintaining a separate class-name keyed table.

## Current State

`ControlConfig` currently defines four kinds of metadata:

- `hidden_fields`: fields omitted from the control panel.
- `general_fields`: fields shown in the top-level general section.
- `beginner_fields`: fields visible in beginner mode.
- `rows`: explicit row grouping for compact control layouts.

Other UI constants, such as `DIAL_FIELDS`, `ENTRY_WIDTHS`, `OPTION_VALUES`, colors, and sizes, are separate concerns and should stay out of this change.

## Plan

1. Add a field metadata type for control-panel layout.

   A small frozen `BaseModel` is enough:

   ```python
   class Control(BaseModel, frozen=True):
       hidden: bool = False
       general: bool = False
       beginner: bool = False
       row: int | None = None
       order: int = 0
   ```

   Add a helper such as `control(...) -> Control` so model fields can use it inside `Annotated`.

2. Annotate fields directly in their data classes.

   Example:

   ```python
   gain: Annotated[
       float,
       tyro_option(aliases=['-G']),
       control(general=True, beginner=True),
   ] = 1.0
   ```

   Fields with no control annotation should keep default behavior: visible, advanced-only, and automatically arranged by `_grid_rows()`.

3. Translate each existing `ControlConfig` entry.

   - `hidden_fields` becomes `control(hidden=True)`.
   - `general_fields` becomes `control(general=True)`.
   - `beginner_fields` becomes `control(beginner=True)`.
   - `rows` becomes `control(row=N, order=M)`.

4. Update `control_panel.py` to read `Annotated` metadata.

   Add helpers that inspect `type(data).model_fields[name].annotation`:

   - `_control_metadata(cls, name) -> Control`
   - `_is_hidden_field(cls, name) -> bool`
   - `_is_general_field(cls, name) -> bool`
   - `_is_beginner_field(data, name) -> bool`
   - `_control_rows(data, fields) -> list[list[str]]`

   `_control_rows()` should group fields with a `row` value, sort each row by `order`, then append unrowed fields using the existing `_grid_rows()` fallback.

5. Replace hard-coded general controls.

   `_general_controls()` should walk the same visible model tree and collect fields annotated with `general=True`, instead of hard-coding:

   - `Tuney.preset`
   - `Tuney.max_gap`
   - `Tuney.hover_time`
   - `Tuney.silent`
   - `Tuney.run_in_background`
   - `MultiPlayer.gain`
   - `MultiPlayer.note_offset`
   - `PitchToFrequency.function`

6. Delete `ControlConfig` and `CONTROL_CONFIGS`.

   Keep unrelated constants in `tuney/ui/constants.py`.

7. Update tests and regression fixtures.

   Existing tests already cover:

   - visible fields
   - beginner-mode filtering
   - compact row layout
   - dial behavior
   - control-panel field names

   Update fixtures only when output intentionally changes.

## Verification

Run the standard checks after implementation:

```sh
uv run pytest
uv run ruff check --fix --select B,E,F,I tuney test/*.py pyinstaller_entrypoint.py
uv run ty check tuney
python_version="$(cat .python-version)"
python_version="${python_version//./}"
find test tuney -name '*.py' | xargs uv run pyupgrade --py"${python_version}"-plus
git diff --check
```

## Additional Work Beyond The Prompt

None.
