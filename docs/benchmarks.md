# Benchmarks

A small but informative agentic-coding suite. Each task ships a failing pytest file and a prompt; the agent must implement, run `./score.sh`, and iterate until it prints `PASS`. Source is in `bench/stress_tests/`.

| # | Task | What it probes |
|---|---|---|
| 01 | LRU cache | Baseline single-file impl. If a model fails this, it's unusable. |
| 02 | Topological sort + cycle detection | Order direction trap, implicit-leaf nodes |
| 03 | Token-bucket rate limiter | Thread safety, injectable clock |
| 04 | B-tree insertion | Hard data structure, lots of state |
| 05 | Mini-grep CLI | Multi-file, argparse, file I/O, shell-tool-heavy |
| 99 | God-class refactor → 6 modules | Read-then-write retention; aggregating validators; no shared state |

## Headless agent loop

`bench/scripts/headless_agent.py` is a ~270-line OpenAI-tool-call loop. It exposes four tools to the model: `write_file`, `read_file`, `run_bash`, `finish`. It is **not** opencode — it's a smaller harness that uses the same NIM endpoint, the same tool-call protocol, and a 15-turn cap. Results here approximate what opencode would observe.

## v0.1 results — single-key NIM free tier

| Model | Score | Notes |
|---|---|---|
| **moonshotai/kimi-k2.6**                       | **6 / 6** | First to ace the suite. Median 3–8 turns per task. 99_refactor was hit by a 429 mid-fix on a single key; retry with the second key landed PASS in 4 turns / 39 s. |
| meta/llama-3.3-70b-instruct                    | 3 / 6     | Passed 01 LRU, 03 rate-limiter, 04 B-tree. Failed 02 toposort (wrong order direction), 05 minigrep (broken `--include` + context lines), 99 refactor (validator short-circuited, pricing off). All three failures hit the 15-turn cap. Zero infra errors. |
| qwen/qwen3-coder-480b-a35b-instruct            | 2 / 3 completed | 01 LRU PASS, 05 minigrep PASS, 04 B-tree FAIL (turn cap, 745 s). Three other tasks killed by NIM infra (`503 ResourceExhausted` and read timeouts). Best coding behavior when it ran, worst reliability. |
| nvidia/llama-3.3-nemotron-super-49b-v1         | 0 / 6     | Emits tool calls as text (`<TOOLCALL>[write_file(...)]`) instead of the OpenAI `tool_calls` field. Unparseable by opencode or any standard agent. Drop. |
| qwen/qwen2.5-coder-32b-instruct                | n/a       | Retired by NVIDIA (`HTTP 410 Gone, EOL 2026-05-12`). |
| google/gemma-4-31b-it                          | n/a       | Catalog-listed but inference endpoint returns 504 / hangs 60 s+. |

## Reproducing

```bash
# install nim-code first (./install.sh)
. ~/.config/nim-code/env
MODEL=moonshotai/kimi-k2.6 bench/scripts/run_suite.sh
```

`SUMMARY.md` lands in `/tmp/nim_suite_<epoch>/`.

## Honest caveats

1. **Six tasks is a small sample.** This is a smoke-test, not a leaderboard. SWE-bench / LiveCodeBench have hundreds of items each; trust those for absolute capability claims.
2. **NIM free-tier limits dominate large-model results.** Qwen3-Coder 480B and Kimi K2.6 both hit 429/503 during sustained runs. A paid NIM endpoint or self-hosted container would close that gap.
3. **The harness uses temperature 0.2 and a 15-turn cap.** Models that need >15 turns are marked FAIL — that's a deliberate ceiling on the agent loop, not a model verdict.
4. **No retry-budget shaping.** Each task is one shot; we don't best-of-N.
