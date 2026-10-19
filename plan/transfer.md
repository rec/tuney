# Transfer

As of 2026-10-19, the local Python 3.15 dependency installation issue described
below is resolved. There is no agreed next change.

## Local Python 3.15 dependency installation fix

The previous lockfile used `pyobjc-core==12.1`, which comes through `pyttsx3`
and has no Python 3.15 wheel. A fresh source build still failed on this macOS
machine with `error: Cannot locate a working compiler`. The currently installed
Apple compiler is Clang 16, so the earlier reference to Clang 15 was stale.

Updated the coupled PyObjC packages in `uv.lock` from 12.1 to 12.2.2. A fresh
installation of `pyobjc-core==12.2.2` downloaded a Python 3.15 wheel successfully.
No compiler overrides or project build settings are needed for this installation.

Verified the full locked dependency set in separate temporary environments:

```sh
UV_PROJECT_ENVIRONMENT=/private/tmp/tuney-transfer-315 \
uv sync --locked --python 3.15 --no-cache

UV_PROJECT_ENVIRONMENT=/private/tmp/tuney-transfer-313 \
uv sync --locked --python 3.13
```

Both installations and `uv lock --check` passed. The project's existing `.venv`
and `.python-version` were left unchanged.

The test suite was not rerun because this change only updates the lockfile and
documentation, following the repository instructions. The older Python 3.15 test
result remains historical and does not validate application behavior with the
updated dependencies.

## Additional work beyond the prompt

None.
