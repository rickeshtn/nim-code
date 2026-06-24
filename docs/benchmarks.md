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

## v0.3 results — local Ollama, community Gemma-4 fable5 fine-tunes + Qwythos blocker (2026-06-24)

First sweep hosted on **Ollama 0.20.2** against the local OpenAI-compatible endpoint at `http://127.0.0.1:11434/v1`. Three changes to the harness made this possible:

1. **Embedded-tool path in `headless_agent.py`.** When `NIM_URL` is localhost, the harness stuffs the tool schemas into the system prompt and drops the OpenAI `tools` field — Ollama 0.20 rejects requests with `tools` for any model whose Modelfile doesn't declare tool support, and no `hf.co/...` auto-pulled GGUF does.
2. **Tool-call normalizer wired into the response path** (`bench/scripts/tool_call_normalizer.py`, vendored from the `gemma4_wClaude` sibling project). Synthesizes OpenAI `tool_calls[]` from text-wrapped output. New `gemma4_native` strategy added for v2's `<|tool_call>call:fn{k:<|"|>v<|"|>}<tool_call|>` format that leaks when Ollama doesn't run `--jinja` over the Gemma-4 template.
3. **CamelCase tool-name aliases** (`WriteFile` → `write_file`, `RunBash` → `run_bash`, etc) — community fine-tunes routinely emit the wrong case and would otherwise burn turns on misspells.

`NIM_TIMEOUT=600`, 15-turn cap, default Ollama runtime (`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, full GPU offload on RTX 3080). `MAX_FAIL=6` — we record outcomes rather than gate.

| Model | Score | Wall (sum) | Notes |
|---|---|---|---|
| [yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2](https://huggingface.co/yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF) (Q4_K_M, local) | **3 / 6** | 755 s | First community ≤12 B to clear three stress tasks on this suite. PASS: 01_lru_cache (3 turns / 21 s), 02_toposort (4 / 21), 03_rate_limiter (8 / 50). FAIL: 04_btree (5 / 142 — quant CoT drift), 05_minigrep (6 / 449 — hit timeout territory), 99_refactor (4 / 74, 1 tool-error — gave up before the 6-file split). Confirms the model card's tau2-bench "agentic" claim is real and degrades on multi-file / large-state tasks. v2 emits Gemma-4 native `<\|tool_call>call:fn{...}<tool_call\|>` content when warmed up; the new `gemma4_native` normalizer strategy parses it cleanly. |
| [yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1](https://huggingface.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF) (Q4_K_M, local) | **1 / 6** | 241 s | **No change vs v0.2 — confirms the regression is the model itself, not the harness.** The new normalizer DID fire (smoke PASS, and `_strat_tag_pycall` matched mid-loop), so this is post-tool-call failure: v1's card explicitly states **no tool-use training**, and the model emits short bursts and stops (median 2 turns/task). PASS: 03_rate_limiter only (single-shot solvable in 1 tool call). Retire v1 from agentic eval. |
| yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1 (Q8_0, local) | 0 / 6 | 346 s | Q8_0 doesn't help — same lack-of-tool-loop training as Q4_K_M, with slower turns. Confirms quant level isn't the lever for v1. |
| yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2 (Q8_0, local) | NO-SCORE × 6 | n/a | Cold-load + Q8_0 inference latency caused `score.sh` never to write PASS/FAIL into the agent log. Needs rerun with model pre-warmed (`ollama run <tag> "warmup" </dev/null` before the sweep) — kept as a placeholder in the local-bench overview at `docs/benchmarks/local/`. |
| [empero-ai/Qwythos-9B-Claude-Mythos-5-1M](https://huggingface.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF) (any quant) | blocked | n/a | Ollama 0.20.2's bundled llama.cpp fails to load with `error loading model architecture: unknown model architecture: 'qwen35'`. The GGUF declares `qwen35.ssm.*` (Qwen 3.5 with the model's own SSM layers); not yet recognised. Re-test on `ollama` upgrade, or run via a recent `llama-server` build directly. |

### Cross-cutting findings (v0.3)

- **v1 vs v2 separation is real.** v1 (coder, no tool-use training) is a code-completion model dressed as an agent; v2 (agentic + tau2-trained) clears three tasks at Q4_K_M. The v0.2 read of "v1 was bad because of tool-call format" was incomplete — format is now fixed (normalizer + embedded tools), but v1 still doesn't sustain the loop. Pick v2 for agent work.
- **Ollama-as-host friction is template-driven, not capability-driven.** Every community GGUF pulled from `hf.co/...` arrives without a tool-aware Modelfile, so Ollama rejects requests with the `tools` field. The fix is harness-side (embed tools in the system message + normalize wrapped output) rather than per-model Modelfile rewriting.
- **`qwen35` arch is the next porting blocker.** Qwythos can't run on this stack until ollama's bundled llama.cpp learns the architecture. Re-evaluate when ollama ships a build off a llama.cpp commit that supports it.

## v0.2 results — NIM availability snapshot + first self-host (2026-06-15)

Re-run after observing widespread free-tier flakiness (TTFB-then-hang on Kimi, Gemma-4, Llama-3.3-70b cold paths; 410 Gone on previously-listed models). Same suite, same 15-turn cap, NIM models hit upstream directly. Local Gemma-4 went through llama.cpp at `:8085` with `NIM_TIMEOUT=600` and `-c 32768`.

| Model | Score | Wall (sum) | Notes |
|---|---|---|---|
| **mistralai/mistral-medium-3.5-128b** | **6 / 6** | 1237 s | New NIM-side leader. Median 3 turns/task; 99_refactor in 8 turns / 566 s. Clean OpenAI `tool_calls[]` throughout, zero parse errors. 128 B dense — fits 2× 80 GB FP8 on self-host. |
| **gemma-4-31b-it (local Q5_K_M, RTX 3080 + P100)** | **6 / 6** | 1241 s | First self-host result. Decode ~12 tok/s. 04_btree was 509 s (7 turns); 99_refactor needed 14 turns / 306 s. Required `--jinja` for tool calls. Original first pass hit harness 120 s urlopen ceiling on 05_minigrep + 99_refactor — both PASSed after raising to `NIM_TIMEOUT=600`. |
| **nvidia/nemotron-3-super-120b-a12b** | **5 / 6** | 1350 s | Strong on the first 5 (median 3 turns/task) but FAIL on 99_refactor at the 15-turn cap (923 s, longest single-task duration in the suite). The Mamba-Transformer hybrid got stuck mid-refactor: kept rewriting files without removing the original `godclass.py`, score.sh kept WARN-then-FAIL. Not a tool-call defect — turn budget exhausted while still iterating. |
| **meta/llama-3.3-70b-instruct** | **4 / 6** | 830 s | PASS: 01, 03, 04, 99. FAIL: 02_toposort (15-turn cap, same wrong-order-direction failure mode as v0.1) and 05_minigrep (15-turn cap, broken `--include` glob). Same failure shape as v0.1 — these are model weak spots, not infra noise. |
| **moonshotai/kimi-k2.6** | **5 / 6** | 154 s | Regression vs v0.1 6/6 on 05_minigrep: NIM's serialization of Kimi's native tool-call sentinels leaked `<\|tool_call_end\|>` into the message content instead of the OpenAI `tool_calls[]` field, the harness gave up at turn 2 with "no tool_calls — ending loop". This is a NIM-side regression, not a Kimi capability change. Fastest wall time of the lineup when warm. |
| **gemma-4-31b-it Q3_K_M (local, single RTX 3080)** | **5 / 6** | 373 s | Same model as the Q5_K_M row but harder quant on a single 20 GB GPU (drop the P100). **3.3× faster total wall** vs Q5_K_M dual-GPU (the P100 had been bottlenecking the 3080 via PCIe tensor parallel). Decode steady at ~25 tok/s. The one regression vs Q5: 99_refactor — Q3 quant got stuck emitting a 4 K-token code dump instead of a tool call, same failure shape as nemotron-120b on the same task. Best speed/quality trade for this hardware tier. |
| [yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1](https://huggingface.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF) (Q4_K_M, community fine-tune) | **1 / 6** | 127 s | Fast decode (~58 tok/s on single 3080, 2.3× the 31B Q3 rate). Tool calls are broken: the model usually emits `<tool_call>fn_name(arg=value)</tool_call>` as raw text in `content` instead of OpenAI `tool_calls[]`. Inconsistent — passed 01_lru_cache with one good tool call, but emitted zero tool calls in the first turn of all five other tasks → harness ended each loop immediately. This is a training-artifact issue with the fine-tune, not a llama.cpp config problem (chat template detected as `peg-gemma4`, same as base Gemma 4 31B which works fine). Stays in the table as a cautionary data point — community fine-tunes can ship with custom non-OpenAI tool-call conventions even when the base architecture supports OpenAI shape. |
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
