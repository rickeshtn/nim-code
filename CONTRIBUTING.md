# Contributing

This is a thin wrapper around [opencode](https://opencode.ai) plus a benchmark harness. Keep PRs small and focused.

## Local checks before submitting

```bash
bash -n install.sh uninstall.sh bench/scripts/run_suite.sh bench/scripts/tool_call_smoke.sh
python3 -m py_compile bench/scripts/headless_agent.py
python3 -c "import json; json.load(open('opencode.json'))"
```

CI runs these automatically (see `.github/workflows/ci.yml`).

## Adding a NIM model

1. Verify with `bench/scripts/tool_call_smoke.sh <model_id>` that it actually emits OpenAI-shaped `tool_calls`. If it emits text-only or a non-standard format (e.g. `<TOOLCALL>...`), do **not** add it — it will fail silently inside `nimcode`.
2. Add an entry under `provider.nim.models` in `opencode.json` with realistic `context` / `output` limits.
3. Optional but recommended: run the full bench suite against it — `MODEL=<id> bench/scripts/run_suite.sh` — and append the result row to `docs/benchmarks.md`.

## Bumping the default model

Change `model` at the top of `opencode.json`. Justify the swap by attaching a fresh bench run in the PR.

## Adding network calls

`install.sh` currently makes at most two outbound calls: one to NIM `/chat/completions` (key validation) and one to GitHub raw (`opencode.json` download, only on `curl|bash` mode). If your PR adds another call, document it in `README.md` under "Privacy" and justify it in the PR description.

## Coding style

- Shell: pass `bash -n`; quote variables; `set -euo pipefail` at top of every script; `set +eu` around any `source` of an external file.
- Python: stdlib only in `bench/scripts/headless_agent.py`. Keep `urllib` over `requests`.
