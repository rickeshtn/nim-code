# nim-code stress tests

Six tasks of increasing difficulty. Each tests a different failure mode of an agentic coding loop on top of NIM-hosted models.

## How to run a single task

```bash
cp -r stress_tests/01_lru_cache /tmp/run_01 && cd /tmp/run_01
nimcode                                  # paste the contents of PROMPT.md
```

The prompt instructs the agent to run `./score.sh` itself and iterate until it prints `PASS`. **This IS the test** — closing the loop is part of what we're measuring.

When the agent stops:
- Look at the last `PASS` / `FAIL` line in the TUI output. That's your score for this task.
- If you need to verify independently or run `score.sh` outside the TUI, open a **second terminal** in the same dir (`cd /tmp/run_01`) — the TUI doesn't lock the files.

You can also tell the agent inline:
> run ./score.sh and tell me what it says

Failure modes worth noting:
- Agent claims `PASS` without running the scorer → model is lying about tool calls. Mark FAIL.
- Agent runs scorer, sees FAIL, gives up → mark FAIL with note "didn't iterate".
- Agent loops indefinitely (>10 iterations) → kill it, mark FAIL with note "couldn't converge".

## What each task probes

| # | Task | Probes |
|---|---|---|
| 01 | LRU Cache | Baseline: single-file impl, deterministic test. If this fails, the model is unusable. |
| 02 | Topological sort + cycle detect | Recursion, edge cases, returning structured results |
| 03 | Token-bucket rate limiter | Time-based logic, threading concerns, mocking time in tests |
| 04 | B-tree insertion | Hard data structure, lots of state — exposes context drift |
| 05 | Mini-grep CLI | File I/O, argparse, shell-tool-heavy, multi-file |
| 99 | Refactor a 200-line god-class | Read-then-write retention; agent must understand existing code first |

## Scoring rubric

For each task, record three numbers:
- **pass**: 1 if `./score.sh` exits 0 on first agent stop, else 0
- **turns**: count of model turns (rough: count agent responses in the TUI)
- **tool_errors**: count of tool calls the agent had to retry due to malformed JSON or wrong args

Per-model overall score = `sum(pass) / 6 * 100`.

## Run across models for comparison

For each model:
1. `nimcode` → `/models` → switch
2. Re-run all six tasks in clean `/tmp/run_XX` copies
3. Fill `RESULTS.md`

Models worth comparing on this harness:
- `meta/llama-3.3-70b-instruct` (default)
- `qwen/qwen2.5-coder-32b-instruct` (coding-specialist)
- `nvidia/llama-3.3-nemotron-super-49b-v1` (NVIDIA-tuned)

Don't bother with `deepseek-r1` (no reliable tool calling) or 405B (latency makes the agent loop painful).
