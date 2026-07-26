# Dark Mode Plan

## Goal

Add a dark mode to Tuney's PySide6 GUI while keeping the existing light mode,
layout behavior, tooltip behavior, note-button states, and platform-specific
window fixes intact.

Dark mode should be a theme choice over the current UI, not a separate UI path.
The implementation should centralize colors first, then switch the active theme
through one palette and stylesheet application point.

Additional work beyond the prompt

None.

## Current State

Tuney already sets the Qt style to `Fusion` and applies a fixed light
application palette in `tuney/ui/main_window.py`. This was added to avoid
Windows dark/system palettes leaking black backgrounds into a mostly light UI.

The current colors are not centralized:

* `tuney/ui/constants.py` defines `WINDOW_BACKGROUND`.
* `tuney/ui/main_window.py` sets `QPalette` roles directly.
* `tuney/ui/control_panel.py` hard-codes control-section background, border, and
  title colors.
* `tuney/ui/note_button.py` hard-codes pressed and released button colors.
* `tuney/ui/transport.py` hard-codes hover colors and icon colors.
* `tuney/ui/tooltip.py` and `tuney/ui/control_panel_scala.py` hard-code yellow
  tooltip colors.
* Validation/error states use direct red styles in `tuney/ui/control_panel.py`.

This means a dark mode cannot be made reliable by only changing the application
palette. Widget stylesheets that set backgrounds or text colors will continue to
force light-mode colors unless they are also theme-aware.

## Design

Introduce a small theme model in the UI layer:

* `ThemeName`: `light` or `dark`.
* `Theme`: color values for window, base, text, buttons, borders, disabled text,
  note-button states, transport states, tooltip colors, and validation colors.
* `LIGHT_THEME`: the current visual colors, moved into one table.
* `DARK_THEME`: a dark, high-contrast table built for repeated use rather than a
  one-note black palette.

Keep the first implementation explicit and local. A small frozen data object or
plain module-level constants are enough. Do not add a new dependency or a CSS-like
theme engine.

Suggested dark colors:

* Window and page background: near charcoal, not pure black.
* Control base: slightly lighter than the window background.
* Section background: one step lighter than base.
* Text: near white.
* Disabled text: mid gray.
* Borders and splitter bars: medium gray.
* Pressed note buttons: green with black or very dark text.
* Released note buttons: dark gray with light text.
* Replay active state: muted violet-gray or green variant that still reads as
  active.
* Error text: warm red with enough contrast on dark backgrounds.
* Tooltips: keep the established yellow tooltip style unless dark mode testing
  shows it is visually jarring. The yellow tooltip is already a recognizable
  Tuney affordance.

## User Control

Add a theme setting in the GUI:

* Put the control in the View menu, near the existing advanced-mode and display
  options.
* Use a checkable action named `Dark Mode`.
* Store the preference in `GlobalConfig`, not the main model autosave. Theme is a
  user-interface preference, not part of a musical configuration.
* Apply the setting before constructing the main layout so widgets are created
  with the correct palette.
* Reapply the theme after toggling without requiring restart.

Do not follow the operating system theme automatically in the first pass. A
manual toggle is simpler, testable, and avoids platform-specific theme detection.
System-theme following can be a later feature if users ask for it.

## Implementation Phases

1. Create `tuney/ui/theme.py`.
   * Define `ThemeName`, `Theme`, `LIGHT_THEME`, `DARK_THEME`, and
     `theme_for_name`.
   * Move `WINDOW_BACKGROUND` into the light theme, or keep the constant as a
     compatibility alias during the same change only if it avoids churn.
   * Add helpers for common style strings such as note-button style, tooltip
     style, control-section style, and transport hover style.

2. Apply the application palette from the active theme.
   * Replace `set_app_palette(app)` with `set_app_theme(app, theme)`.
   * Set at least `Window`, `Base`, `AlternateBase`, `Button`, `Text`,
     `WindowText`, `ButtonText`, `ToolTipBase`, and `ToolTipText`.
   * Keep the `Fusion` style, since it gives more predictable cross-platform
     palette behavior than native styles.

3. Add theme persistence.
   * Add a `theme` field to `GlobalConfig`.
   * Default to `light` to preserve current behavior.
   * Save immediately when the user toggles dark mode.
   * Add validation so unknown values fall back through the existing pydantic
     model path rather than requiring manual parsing.

4. Make hard-coded widget styles theme-aware.
   * Convert control-section styles in `control_panel.py`.
   * Convert note-button pressed and released styles in `note_button.py`.
   * Convert transport hover and active replay styles in `transport.py` and
     `layout.py`.
   * Convert validation/error text styles in `control_panel.py`.
   * Decide whether Scala-browser and general tooltip yellow styles remain
     constant or become theme values.

5. Add a View-menu toggle.
   * Add the action in `main_menu.py`.
   * Add a `MainWindow.on_dark_mode` handler.
   * Reapply the app palette and refresh existing widget styles after toggling.
   * Keep the action state synchronized in `sync_config_actions`.

6. Refresh existing widgets after a theme change.
   * Rebuild or restyle the control panel.
   * Reapply note-button styles without changing pressed/released state.
   * Reapply transport and replay styles without changing playback state.
   * Update splitter handles by calling `update()` on the splitter and handles.
   * Keep text contents, focus, undo history, scroll position, and selected
     controls unchanged.

7. Add focused tests.
   * Theme lookup returns the light and dark palettes.
   * `set_app_theme` sets the expected Qt palette roles.
   * The `Dark Mode` menu action reflects `GlobalConfig.theme`.
   * Toggling dark mode saves the config and reapplies theme styles.
   * Note-button style changes with the theme while preserving `is_press`.
   * Control-section styles use theme colors instead of hard-coded light values.

## Risks

The biggest risk is partial theming. If only the top-level palette changes, Qt
widgets with explicit light stylesheets will still look wrong. The first phase
must find and replace direct color literals used for normal UI surfaces.

The second risk is changing behavior while restyling. Theme toggling should not
recreate the app model, restart audio, clear text, reset undo history, or change
window geometry.

The third risk is low contrast in dense controls. Dark mode should be validated
with screenshots of:

* normal startup
* advanced control panel
* Scala browser active and inactive
* note buttons pressed and released
* text-timing view
* replay and transport controls
* error and report-problem dialogs

## Verification

Run the normal Python checks after implementation:

```sh
uv run pytest
uv run ruff check --fix --select B,E,F,I tuney test install/pyinstaller_entrypoint.py experiments/pyside_resize_repro.py experiments/resize_repro.py
uv run ruff format
uv run ty check tuney
version=$(cat .python-version)
version=${version//./}
find test tuney -name \*.py | xargs uv run pyupgrade --py${version}-plus
git diff --check
```

Manual checks should include macOS and Windows screenshots in both light and dark
mode. Windows needs specific attention because the current light palette was
added to prevent black system-palette backgrounds from leaking into the UI.
