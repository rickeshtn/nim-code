Paste into nimcode:

---

Build a CLI tool `mg` (executable script `mg.py`) — a minimal grep. Spec:

    mg [-A N] [-B N] [--include PATTERN] PATTERN [PATH ...]

- Recursively searches PATH(s); default `.`.
- Prints matching lines as `path:lineno:content`.
- `-A N` includes N lines of trailing context (prefix with `-`).
- `-B N` includes N lines of leading context.
- `--include "*.py"` filters by glob on file basename (may be repeated).
- Exit 0 if any match, 1 if none, 2 on error.
- Binary files (heuristic: NUL byte in first 8 KB) are skipped silently.

Fixtures will be created automatically by the test's `setup_module`. Then run `./score.sh`. If it prints `FAIL`, fix and re-run. Only stop when it prints `PASS`. Do not modify the test file.
