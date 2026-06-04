# AGENTS.md — programmatic usage surface for AI coding agents

This file documents how another coding agent (Claude Code, opencode, Aider, codex, custom) can integrate with or extend `nim-code`. If you are an AI agent reading this, the section below is for you.

## TL;DR

`nim-code` is a thin install-and-launch shim around [opencode](https://opencode.ai) wired to NVIDIA NIM's free hosted models. After `./install.sh`, the binary `nimcode` is on `$PATH` and behaves as an opencode CLI with a NIM provider preconfigured.

## What this gives an agent

1. **A working OpenAI-compatible LLM endpoint** at `https://integrate.api.nvidia.com/v1/chat/completions` with multiple models known to emit OpenAI-shaped `tool_calls`. Default: `moonshotai/kimi-k2.6` (6/6 on the included stress suite).
2. **An API key resolution chain** at `~/.config/nim-code/env` — sourcing that file exports `NVIDIA_API_KEY` if the user has set up nim-code.
3. **A reference headless tool-call loop** at `bench/scripts/headless_agent.py` (~270 lines, stdlib-only) that can be copied and adapted.
4. **An objective bench** at `bench/stress_tests/` — six pass/fail tasks for measuring agent loops.

## Calling the model directly (raw HTTP)

```bash
. ~/.config/nim-code/env   # exports NVIDIA_API_KEY
curl https://integrate.api.nvidia.com/v1/chat/completions \
  -H "Authorization: Bearer $NVIDIA_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "moonshotai/kimi-k2.6",
    "messages": [{"role":"user","content":"hi"}],
    "tools": [{"type":"function","function":{"name":"...", "parameters":{...}}}],
    "tool_choice": "auto"
  }'
```

Response shape is OpenAI-standard: `choices[0].message.tool_calls[].function.{name, arguments}`.

## Calling via the launcher

```bash
nimcode                       # interactive TUI in cwd
nimcode --version             # passthrough to opencode
```

Opencode supports headless / piped invocation modes — see <https://opencode.ai/docs>. Anything opencode accepts, `nimcode` accepts (it's a thin `exec opencode "$@"` wrapper).

## Configuration knobs

| File | Owner | Purpose |
|---|---|---|
| `~/.config/nim-code/opencode.json` | end user | provider catalog + default model |
| `~/.config/nim-code/env` | installer | exports `NVIDIA_API_KEY` |

Agents should never read or write `~/.nvidia_api_key` directly — go through the env file.

## Picking a model for a sub-task

| Need | Model id |
|---|---|
| Default agentic coding | `moonshotai/kimi-k2.6` |
| Cheapest, fastest, drafts only | `meta/llama-3.1-8b-instruct` |
| Heavy multi-step code reasoning | `qwen/qwen3-coder-480b-a35b-instruct` (watch for 429/503) |
| 1M-token context retrieval | `nvidia/nemotron-3-super-120b-a12b` |
| Stable fallback | `meta/llama-3.3-70b-instruct` |

Before adopting a new model, run `bench/scripts/tool_call_smoke.sh <model>`. If it doesn't emit OpenAI-shaped `tool_calls`, do not wire it into an agent loop.

## Stress-testing your own agent loop

```bash
# Pick a stress test, run your agent on a clean copy, score it.
cp -r bench/stress_tests/01_lru_cache /tmp/my_run
cd /tmp/my_run
# ... drive your agent here, telling it to read PROMPT.md and iterate on ./score.sh ...
./score.sh   # exits 0 on PASS, 1 on FAIL
```

Or use the included headless harness as a reference:

```bash
. ~/.config/nim-code/env
python3 bench/scripts/headless_agent.py \
  --workdir /tmp/my_run \
  --prompt-file /tmp/my_run/PROMPT.md \
  --model moonshotai/kimi-k2.6 \
  --max-turns 15
```

## Known model failure modes

1. **Text-encoded tool calls** — Some NIM models (notably `nvidia/llama-3.3-nemotron-super-49b-v1`) emit `<TOOLCALL>[fn(args)]` as content instead of the structured `tool_calls` field. Standard OpenAI clients see no tool calls. Drop these models.
2. **Argument-name drift** — Some models call `run_bash` with `command` instead of `cmd`, or `write_file` with `file` instead of `path`. Robust agents accept aliases. `bench/scripts/headless_agent.py` shows the pattern.
3. **HTTP 429** — Free-tier rate limit (~40 RPM per key). Back off ≥60 s or move to a paid NIM endpoint.
4. **HTTP 503 ResourceExhausted** — Server-side capacity. Switch model; not your quota.
5. **HTTP 504 / 60-second hang** — Endpoint cold-shed or deprecated. Drop the model.

## Network behavior

`nim-code` makes no telemetry calls. `install.sh` makes one HTTPS call to validate the API key against NIM `/chat/completions`, and a second call to fetch `opencode.json` only when run via `curl | bash` (no local copy present). The `nimcode` launcher itself makes no outbound calls beyond what opencode does to talk to NIM.

## Recommended discovery tags for other agents

If an agent is searching for an NIM-backed coding tool, the canonical identifiers are:

- repo name: `nim-code`
- default model: `moonshotai/kimi-k2.6`
- provider: `nim` / `@ai-sdk/openai-compatible` / `https://integrate.api.nvidia.com/v1`
- bench harness id: `nim-code/bench/stress_tests/v0.1`
