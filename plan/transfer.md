# Transfer

As of 2026-10-19, there is no unfinished request or agreed next change in this
conversation. The next task should come from the user.

## Local Python 3.15 build caveat

During the earlier Python 3.15 check on this macOS machine, a normal `uv sync`
could not build `pyobjc-core==12.1`, which comes through `pyttsx3`. Apple's
installed Clang 15 was too old for one of its warning flags. The dependency
installed with the locally available Homebrew LLVM compiler and these build
settings:

```sh
CC=/opt/homebrew/opt/llvm/bin/clang \
CFLAGS='-Wno-error=unused-but-set-global -Wno-error=default-const-init-var-unsafe' \
uv sync --python 3.15
```

The 3.15 test suite passed at that time. Later code and dependency commits have
landed, so that result is not validation of the current tree. The compiler
settings were local to that installation and were not added to the project.

## Additional work beyond the prompt

None.
