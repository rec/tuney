# Handover

## Manual Validation Still Needed

The automated suite does not exercise real GUI window-manager behavior, physical
audio devices, or physical MIDI devices. Before a release that affects any of
these areas, test the packaged application on its target platform.

- On macOS, drag every window edge and corner, particularly diagonal resize
  gestures. Check for a crash, a delayed size jump after mouse release, and an
  unusably small control panel.
- On Windows, open, close, and reopen the application repeatedly. Confirm that
  the top of the window remains reachable and that the restored position does
  not move between launches.
- On Windows, check normal and dark mode for consistently painted backgrounds.
- With MIDI enabled, connect and disconnect both input and output devices while
  Tuney is open. Confirm that the control panel refreshes, vanished selections
  are cleared with an actionable dialog, and a newly available device can be
  selected without restarting.
- Test an unavailable MIDI output device. The failure must be visible to the
  user, must disable output, and must allow a later retry after the device
  becomes available.

## Resize Safety

Avoid Qt top-level minimum-size APIs for the main window unless a small native
reproduction proves they are safe on the target macOS version. Previous work
found that enforcing minimum dimensions during a drag can cause both resize
jumps and platform instability. The current deferred enforcement is a
workaround, not evidence that Qt's native minimum-size behavior is universally
safe.

If resize behavior needs further change, prefer a structure in which the outer
window can remain responsive while inner content has its own stable layout,
rather than increasing the top-level minimum repeatedly.

## Diagnostics

Tuney configures logging through Reccy. A packaged application writes its log
to the application state directory by default. Set `RECCY_LOG_PATH` before
launch to choose a different log file. The log is the first artifact to obtain
after a crash or device-open failure.

Issue reports can include a self-snapshot. Treat it as potentially sensitive:
it can capture text and configuration visible in the application window. Ask a
reporter to review the snapshot and log before sharing them.

For a suspected restore defect, preserve the autosave state file and log from
the same run. The state file is more useful than a verbal description because
it contains the exact saved geometry and configuration that led to the result.

## Release Checks

Release builds need a packaging smoke test in addition to source-level checks.
Confirm that the bundled executable starts, opens Help, creates a log on a
handled failure, and can find the packaged Scala data. On Windows and macOS,
test the archive or app bundle in a fresh location rather than from the build
directory.

Unsigned release builds can trigger operating-system or antivirus warnings.
Distribute only through the official release assets, and keep the existing
tester instructions aligned with the archive names and platform behavior.
