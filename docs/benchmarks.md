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

## v0.2 results — NIM availability snapshot + first self-host (2026-06-15)

Re-run after observing widespread free-tier flakiness (TTFB-then-hang on Kimi, Gemma-4, Llama-3.3-70b cold paths; 410 Gone on previously-listed models). Same suite, same 15-turn cap, NIM models hit upstream directly. Local Gemma-4 went through llama.cpp at `:8085` with `NIM_TIMEOUT=600` and `-c 32768`.

| Model | Score | Wall (sum) | Notes |
|---|---|---|---|
| **gemma-4-31b-it (local Q5_K_M, RTX 3080 + P100)** | **6 / 6** | ~1240 s | First self-host result. Decode ~12 tok/s. 04_btree was 509 s (7 turns); 99_refactor needed 14 turns / 306 s. Required `--jinja` for tool calls. Original first pass hit harness 120 s urlopen ceiling on 05_minigrep + 99_refactor — both PASSed after raising to `NIM_TIMEOUT=600`. |
| **nvidia/nemotron-3-super-120b-a12b** | **≥ 5 / 6 confirmed** (in flight at publish) | ~427 s for 5 | Strong performer. Median 3 turns / task; 05_minigrep needed 6. Was warm throughout. First model in lineup to pass 02_toposort cleanly. |
| **meta/llama-3.3-70b-instruct** | **4 / 6** | ~830 s | PASS: 01, 03, 04, 99. FAIL: 02_toposort (15-turn cap, same wrong-order-direction failure mode as v0.1) and 05_minigrep (15-turn cap, broken `--include` glob). Same failure shape as v0.1 — these are model weak spots, not infra noise. |
| **moonshotai/kimi-k2.6** | **5 / 6** | ~154 s | Regression vs v0.1 6/6 on 05_minigrep: NIM's serialization of Kimi's native tool-call sentinels leaked `<\|tool_call_end\|>` into the message content instead of the OpenAI `tool_calls[]` field, the harness gave up at turn 2 with "no tool_calls — ending loop". This is a NIM-side regression, not a Kimi capability change. |
| qwen/qwen3-coder-480b-a35b-instruct | n/a | n/a | Retired by NVIDIA in 2026. Returns 410 Gone. Removed from lineup. |
| google/gemma-4-31b-it | n/a (NIM) | n/a | Catalog-listed but TTFB-then-hang: 140 ms to first byte, then 15+ s of silence with no body. Use local Q5_K_M instead. |
| qwen/qwen3-next-80b-a3b-instruct | n/a | n/a | Cold-timeout (>25 s) for hours; not currently benchable on free tier. |
| mistralai/codestral-22b-instruct-v0.1 | n/a | n/a | 404 Not Found — endpoint deprovisioned despite catalog membership. |
| meta/codellama-70b | n/a | n/a | 404 Not Found. |
| nvidia/llama-3.3-nemotron-super-49b-v1.5 | excluded | n/a | Still emits tool calls as `<TOOLCALL>[...]` text inside content. Unparseable. |

### Cross-cutting findings (v0.2)

1. **NIM free-tier model availability is the dominant variable.** Of 4 code-tuned NIM models we tried to add (qwen3-coder-30b, mistral-small-3.2, codestral-22b, qwen3-next-80b), 2 don't exist in catalog and 2 return 404 / hang. The catalog list is misleading without a live probe.
2. **TTFB-then-hang signature.** On in-demand models (kimi, gemma-4-31b), TTFB ~140 ms is consistent across runs, but the response body never arrives. This is queue-deprioritization at the NVIDIA LB, not your network. Symptom can be diagnosed with `curl -w "TTFB=%{time_starttransfer}s total=%{time_total}s"`.
3. **Local self-host eliminates all NIM-side failure modes.** Gemma-4-31B Q5_K_M on a 36 GB consumer rig hit 6/6. Cost: 5–10× wall-time vs warm NIM. Reliability: 100 %.
4. **Harness defaults were NIM-tuned.** `urlopen(timeout=120)` and `-c 24576` context both bit local hosting until raised. Both are now env-overridable (`NIM_TIMEOUT`, `setup.sh` patches).

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
