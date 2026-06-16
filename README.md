# nim-code

> **A free, terminal-based AI coding agent powered by NVIDIA NIM and Kimi K2.6.** Think Claude Code or Codex, but using free hosted models from `build.nvidia.com`.

[![CI](https://github.com/rickeshtn/nim-code/actions/workflows/ci.yml/badge.svg)](https://github.com/rickeshtn/nim-code/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Default Model: Kimi K2.6](https://img.shields.io/badge/default--model-kimi--k2.6-purple)](https://huggingface.co/moonshotai/Kimi-K2.6)
[![Bench: 6/6 PASS](https://img.shields.io/badge/bench-6%2F6%20PASS-brightgreen)](docs/benchmarks.md)

**Keywords:** NVIDIA NIM, build.nvidia.com, Kimi K2.6, Moonshot AI, free coding agent, terminal coding agent, Claude Code alternative, Codex alternative, opencode, agentic coding CLI, OpenAI tool calls, free LLM API, NIM provider, Qwen3 Coder, Llama 3.3, hosted LLM, AI pair programmer.

---

## What it does

`nimcode` drops you into a Claude-Code-style TUI in any project directory. It can read, write, run, edit files; execute shell commands; iterate on test failures — all backed by hosted models at `build.nvidia.com` that are free to use.

```
$ cd ~/my-project
$ nimcode
> implement an LRU cache in lru.py, then run pytest until green
```

Under the hood it's [opencode](https://opencode.ai) with a preconfigured NIM provider, an auto-validating installer, and a benchmark harness so you can prove the default model actually works before relying on it.

## TL;DR

Grab a free `nvapi-...` key from <https://build.nvidia.com> (any model → **Get API Key**), then:

```bash
# Single key (most users)
printf '%s\n' 'nvapi-PASTE_YOUR_KEY_HERE' > ~/.nvidia_api_key && chmod 600 ~/.nvidia_api_key
curl -fsSL https://github.com/natkal-coder/nim-code/releases/latest/download/nimcode-installer.sh | bash
nimcode
```

**Have multiple keys (from multiple NVIDIA accounts)?** Put them all in the file — one per line. No limit on how many. The installer detects multi-key automatically and the proxy round-robins across all of them:

```bash
# N keys → ~N×40 RPM combined (each stays under per-key 40 RPM cap)
cat > ~/.nvidia_api_key <<'EOF'
nvapi-FIRST_KEY_HERE
nvapi-SECOND_KEY_HERE
nvapi-THIRD_KEY_HERE
# add as many as you have — no upper limit
EOF
chmod 600 ~/.nvidia_api_key
curl -fsSL https://github.com/natkal-coder/nim-code/releases/latest/download/nimcode-installer.sh | bash
nimcode
```

Done. Single-file installer (~24 KB, `opencode.json` + rate-limit proxy baked in). Works on **Linux and macOS** (Intel + Apple Silicon). Needs Node ≥20 (`nodejs.org` LTS or `brew install node`) and Python ≥3.8.

> **macOS note:** `~/.local/bin` isn't on `PATH` by default. The installer warns and tells you what to add to `~/.zshrc`. Or symlink: `sudo ln -s ~/.local/bin/nimcode /usr/local/bin/nimcode`.

---

## Install paths (if the TL;DR doesn't fit)

<details>
<summary><b>One-liner from <code>main</code> (always tracks HEAD, may be unstable)</b></summary>

```bash
curl -fsSL https://raw.githubusercontent.com/natkal-coder/nim-code/main/install.sh | bash
nimcode
```

The installer downloads `opencode.json` from upstream on the fly. Useful when you want bleeding-edge config but accept that `main` can break.
</details>

<details>
<summary><b>Pinned single-file (for reproducible installs)</b></summary>

Replace `v0.1.0` with the tag you want:

```bash
curl -fsSLO https://github.com/natkal-coder/nim-code/releases/download/v0.1.0/nimcode-installer-v0.1.0.sh
chmod +x nimcode-installer-v0.1.0.sh
./nimcode-installer-v0.1.0.sh
```
</details>

<details>
<summary><b>Clone + run (for contributors)</b></summary>

```bash
git clone https://github.com/natkal-coder/nim-code && cd nim-code
./install.sh        # interactive prompt available — no need to pre-save the key
nimcode
```

This is the only path that can show an interactive key prompt (the piped paths have no tty).
</details>

## Get a free NVIDIA API key

1. Open <https://build.nvidia.com>, sign in (free, no credit card).
2. Pick any model → **Get API Key** → copy the `nvapi-...` token.
3. (Recommended) Save it once, the installer auto-detects it on every machine:

   ```bash
   printf '%s\n' 'nvapi-XXXXXXXX...' > ~/.nvidia_api_key
   chmod 600 ~/.nvidia_api_key
   ```

## What `install.sh` does

1. Verifies Node ≥20 + npm.
2. `npm i -g opencode-ai` (skipped if already installed).
3. Writes `~/.config/nim-code/opencode.json` — the NIM provider catalog, Kimi K2.6 default.
4. Resolves your `nvapi-...` key from (in order): `$NVIDIA_API_KEY`, `~/.nvidia_api_key`, previous install, interactive prompt.
5. Validates it against the live NIM `/chat/completions` endpoint.
6. Installs `~/.local/bin/nimcode` — a launcher that loads env + execs opencode with our config.

Idempotent. Pass `--reset` to wipe stored config and re-detect.

## Model lineup

Configured in `opencode.json`. Switch in-session with `/models`.

| Model | Role | Score on our bench |
|---|---|---|
| **`mistralai/mistral-medium-3.5-128b`** | **NIM leader v0.2** — clean tool calls, 128B dense | **6 / 6** |
| `gemma-4-31b-it (local Q5_K_M)` | **self-host** — llama.cpp, no NIM, no quota | **6 / 6** (see Self-hosting section) |
| `gemma-4-31b-it (local Q3_K_M, single 3080)` | self-host, harder quant | 5 / 6 (3.3× faster than Q5 dual; FAIL 99_refactor only) |
| `moonshotai/kimi-k2.6` | NIM default in `opencode.json`, 1T MoE | **6 / 6** (v0.1) · **5 / 6** (v0.2 — NIM-side sentinel-leak regression) |
| `nvidia/nemotron-3-super-120b-a12b` | NIM, 120B MoE / 12B active, 200 K ctx | 5 / 6 (v0.2 — FAIL 99_refactor at 15-turn cap) |
| `meta/llama-3.3-70b-instruct` | NIM, dense 70B, stable when warm | 4 / 6 (v0.2, up from 3 / 6 in v0.1 — same two tasks fail) |
| [`yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1`](https://huggingface.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF) (Q4_K_M, community) | self-host, HF fine-tune, 12B | **1 / 6** — fast (58 tok/s) but tool-call format incompatible (see notes) |
| `qwen/qwen3.5-122b-a10b` | NIM, general-purpose alt | not benchable (cold-timeout in v0.2 probe) |
| `meta/llama-3.1-8b-instruct` | NIM, small/fast (opencode `small_model` slot) | n/a |
| ~~`qwen/qwen3-coder-480b-a35b-instruct`~~ | retired by NVIDIA (410 Gone) | removed in v0.3.3 |

Methodology + per-task results: [`docs/benchmarks.md`](docs/benchmarks.md).

## Skills and slash commands

nimcode ships with built-in skills and slash commands that work in every session. Type `/` in the TUI to see what's available.

| Built-in | Type | What it does |
|----------|------|---|
| `/load-graph` | command | Rehydrate context from `.agent-memory/graph/latest.md` at the start of a session |
| `compact-graph` | skill | Compress the current session into a knowledge graph — pair with `/load-graph` next session |

Write your own:

```bash
# Slash command — type /explain <file> in the TUI
cat > ~/.config/opencode/commands/explain.md <<'EOF'
Explain what $ARGUMENTS does — data flow, edge cases, anything that looks wrong.
EOF

# Skill — the model invokes it when the description matches
mkdir -p ~/.config/opencode/skill/security-review
cat > ~/.config/opencode/skill/security-review/SKILL.md <<'EOF'
---
name: security-review
description: Audit code for OWASP Top 10. Use when the user asks for a security review.
allowed-tools: Read, Grep, Bash
---
# Security Review
1. Trace user inputs to sinks (SQL, shell, templates)
2. Flag any unsanitized path
3. Output: numbered findings with severity, file:line, fix suggestion
EOF
```

Already use Claude Code? Run `nimcode sync-claude` to import your `~/.claude/skills` and `~/.claude/commands` into nimcode.

Full guide: [`docs/skills-and-commands.md`](docs/skills-and-commands.md) — covers per-project skills, loading order, troubleshooting, and example libraries.

## Session management

```bash
nimcode                              # new session
nimcode -c                           # continue the last session
nimcode -s ses_164807e71ffe...       # resume a specific session by ID
nimcode --fork -s ses_164807e71ffe.. # fork a session (branch off without modifying the original)
nimcode sessions                     # list all sessions
nimcode rename ses_164807e71ffe... "My project refactor"  # rename a session
```

Session IDs are shown in the opencode UI on exit (the `Continue` line) and by `nimcode sessions`.

## For AI coding agents

If another coding agent (Claude Code, opencode, Aider, you) wants to **invoke nimcode programmatically** rather than via TUI:

```bash
# Send a one-shot prompt, get a response, exit
nimcode run "implement an LRU cache in lru.py"

# Or use the underlying NIM API directly with the same config:
. ~/.config/nim-code/env
curl https://integrate.api.nvidia.com/v1/chat/completions \
  -H "Authorization: Bearer $NVIDIA_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"model":"moonshotai/kimi-k2.6","messages":[{"role":"user","content":"..."}]}'
```

The headless agent harness under `bench/scripts/headless_agent.py` is a 270-line, dependency-free OpenAI-tool-call loop that another agent can copy and adapt — it exposes `write_file`, `read_file`, `run_bash`, `finish`. See [`AGENTS.md`](AGENTS.md) for the full agent integration surface.

## Privacy

nim-code does **not** send any telemetry. The installer makes exactly one network call (validating your key against NIM's `/chat/completions`) and one optional call to download `opencode.json` if you used the `curl|bash` path. No usage data leaves your machine.

## Repo layout

```
.
├── install.sh              # one-shot installer
├── uninstall.sh
├── opencode.json           # NIM provider catalog (Kimi K2.6 default)
├── AGENTS.md               # programmatic usage surface for other agents
├── docs/
│   ├── benchmarks.md       # stress-suite methodology + results
│   └── troubleshooting.md
└── bench/                  # developer tooling — not needed to use nimcode
    ├── scripts/
    │   ├── headless_agent.py    # 270-line OpenAI tool-call loop
    │   ├── run_suite.sh         # bulk bench runner
    │   └── tool_call_smoke.sh   # verify a NIM model emits real tool_calls
    └── stress_tests/            # six pass/fail coding tasks
```

## Honest limits

- **NIM context windows** are often capped below a model's native max. Long sessions silently truncate.
- **No prompt caching** — every turn re-bills full context. Expensive vs. Claude/Gemini for long sessions.
- **Free-tier rate limits**: ~40 RPM per key. Heavy use needs paid NIM or self-hosted NIM container.
- **Some catalog-listed models are unusable.** Endpoint health and tool-call format compatibility vary — `bench/scripts/tool_call_smoke.sh <model>` filters them.

## Rate-limit handling (throttled by default in v0.2+)

NIM free tier caps at ~40 requests/minute per key. Agent loops burst above that and get 429'd mid-run. **Starting in v0.2, `nimcode` runs all traffic through a local rate-limit proxy by default** so this never happens. You don't need to opt in — `nimcode` just works without 429s.

### What the proxy does

- **Token bucket**: caps at 38 RPM per key (2 under NVIDIA's 40 to be safe)
- **Minimum 5s gap between calls per key** (default — set via `NIM_MIN_INTERVAL`)
- **Multi-key round-robin** when you configure more than one key (see below)
- **Blocking acquire** — requests queue and wait when the bucket is empty, never return 429 to opencode

Implementation: `~/.config/nim-code/nim_proxy.py` (Python stdlib only, ~280 lines). Started automatically by the `nimcode` launcher; cleaned up on exit.

### Multi-key setup (N keys = ~N×40 RPM)

Put any number of `nvapi-...` keys in `~/.nvidia_api_key`, one per line:

```bash
cat > ~/.nvidia_api_key <<'EOF'
nvapi-KEY_ONE
nvapi-KEY_TWO
nvapi-KEY_THREE
# no upper limit — add as many keys as you have
EOF
chmod 600 ~/.nvidia_api_key
./install.sh   # re-run to refresh — env file detects multi-key automatically
nimcode
```

Comma-separated on one line also works (`nvapi-A,nvapi-B,nvapi-C`). Comments (`#`) and blank lines are ignored.

The proxy round-robins across all keys — effective RPM = N × 38 (per-key cap), with each key independently staying under NVIDIA's 40 RPM limit. 3 keys = ~114 RPM, 5 keys = ~190 RPM, etc.

If you'd rather not put keys in a file, set `NIM_KEYS` as an env var instead:

```bash
NIM_KEYS="nvapi-A,nvapi-B,nvapi-C" nimcode
```

`NIM_KEYS` (env) overrides `~/.nvidia_api_key` (file) when both are set.

**Honest note:** Getting multiple NIM keys requires multiple NVIDIA developer accounts (each phone-verified). That's friction NVIDIA imposes, not something nim-code can shortcut.

### Tuning knobs (env vars)

| Var | Default | Effect |
|---|---|---|
| `NIM_KEYS` | unset | comma-separated keys for round-robin; overrides `NVIDIA_API_KEY` |
| `NIM_MIN_INTERVAL` | `5` | min seconds between calls per key; `0` disables the gate |
| `NIM_RPM` | `38` | token-bucket cap per key |
| `NIM_PROXY_PORT` | `8123` | port the proxy binds to |
| `NIM_UPSTREAM` | `https://integrate.api.nvidia.com` | upstream NIM endpoint |

### Disabling throttling

For paid NIM endpoints or self-hosted NIM containers where rate limits don't apply, edit `~/.config/opencode/opencode.json` and change:

```json
"baseURL": "http://127.0.0.1:8123/v1"
```

back to:

```json
"baseURL": "https://integrate.api.nvidia.com/v1"
```

Re-running `./install.sh` will overwrite this with the throttled default, so document the change for yourself or maintain a paid-config fork. ~250 lines.

## Self-hosting (skip NIM entirely)

NIM's free tier has problems beyond rate limits — in-demand models (Kimi K2.6, Gemma 4 31B, Llama 3.3 70B) frequently exhibit **TTFB-then-hang**: the upstream load balancer accepts the connection in ~140 ms, then returns no body for 15–60 s with no `Retry-After`, no 503, no signal. Quotas are per-model and per-day; daily caps on the larger models can be exhausted by a single agent-heavy session. Self-hosting removes all of this.

### Option A — local llama.cpp + Gemma 4 31B (no quota, no queueing)

Verified on a dual-GPU desktop (RTX 3080 20 GB + Tesla P100 16 GB, tensor-split 17,12). **Bench: 6/6 PASS**, agent wall-time ~21 min vs ~3 min on a warm NIM. ~287 tok/s prompt eval, ~12 tok/s decode.

```bash
# 1. Build llama.cpp with CUDA (Blackwell/Hopper/Ada/Ampere supported)
git clone https://github.com/ggerganov/llama.cpp ~/llama.cpp
cd ~/llama.cpp
cmake -B build -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"

# 2. Download Gemma 4 31B Q5_K_M (~22 GB)
mkdir -p ~/models/gemma4
hf download bartowski/google_gemma-4-31B-it-GGUF \
  --include google_gemma-4-31B-it-Q5_K_M.gguf \
  --local-dir ~/models/gemma4

# 3. Start llama-server (single-GPU users: drop --tensor-split)
~/llama.cpp/build/bin/llama-server \
  -m ~/models/gemma4/google_gemma-4-31B-it-Q5_K_M.gguf \
  -ngl 99 --tensor-split 17,12 -fa on --jinja \
  -c 32768 --cache-reuse 256 \
  --host 0.0.0.0 --port 8085 &

# 4. Add a local provider to ~/.config/opencode/opencode.json
# (insert under "provider": { ... } alongside the "nim" entry)
```

```json
"gemma": {
  "npm": "@ai-sdk/openai-compatible",
  "name": "Gemma 4 (local llama-server)",
  "options": {
    "baseURL": "http://127.0.0.1:8085/v1",
    "apiKey": "none"
  },
  "models": {
    "google_gemma-4-31B-it-Q5_K_M.gguf": {
      "name": "Gemma 4 31B Q5_K_M (local) — llama-server on :8085",
      "tool_call": true,
      "limit": { "context": 32768, "output": 4096 }
    }
  }
}
```

```bash
# 5. Run against local Gemma — no NIM key required
nimcode -m gemma/google_gemma-4-31B-it-Q5_K_M.gguf
```

Tested gotchas:

- **Port conflicts.** Pick a free port for `--port`. ClearML's `clearml-fileserver` container holds 8081; many ML stacks squat 8080. `ss -tln | grep :PORT` before launching.
- **Context window vs system prompt.** opencode's agent system prompt is ~15 K tokens. `-c 24576` (llama.cpp default) leaves only ~9 K for the actual session — `04_btree` style tasks overflow. Use **`-c 32768`** minimum; `-c 49152` if VRAM allows.
- **Bench harness timeout.** `bench/scripts/headless_agent.py` defaults `urlopen(timeout=120)`. At Gemma's ~12 tok/s local decode, a 4 K-token reply needs ~340 s. Set `NIM_TIMEOUT=600` (env var) when benching local models — supported in v0.3.3+.
- **Tool calls.** Gemma 4 31B emits proper OpenAI `tool_calls[]` via llama.cpp's `--jinja` template loader. Drop `--jinja` and you'll get the function call in `content` as a sentinel-wrapped string and the harness will fail silently.

### Trying community fine-tunes from HuggingFace

You can point llama.cpp at any GGUF from HuggingFace — `hf download <repo> --include "*.gguf" --local-dir ...` then `llama-server -m <path>` is the whole recipe. The trap is **tool-call format compatibility**: even when the base architecture supports OpenAI `tool_calls[]` (verified for the base model), the fine-tune may have trained on a different convention and silently fall back to it.

Real example from our v0.2 bench: [`yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF`](https://huggingface.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF) (Q4_K_M, 6.9 GB) is **fast** — ~58 tok/s decode on the single-3080 baseline, 2.3× the 31B Q3 rate — but it emits `<tool_call>fn_name(arg=value)</tool_call>` as raw text in the message `content` instead of OpenAI structured `tool_calls[]`. Got 1/6 on the bench because the harness can't parse that format. The base Gemma 4 31B works fine on the same harness with the same `--jinja` flag, so this is a training-artifact mismatch in the fine-tune, not a llama.cpp config issue.

What to do before committing to a community fine-tune for agent use:

1. **Probe its tool-call shape with a one-liner before benching**:

    ```bash
    curl -sS -X POST http://127.0.0.1:8085/v1/chat/completions \
      -H "Content-Type: application/json" -d '{
        "model":"<the gguf id>",
        "messages":[
          {"role":"system","content":"You have one tool: write_file. Use it."},
          {"role":"user","content":"Write hello to test.txt"}
        ],
        "tools":[{"type":"function","function":{"name":"write_file","description":"write","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}}],
        "tool_choice":"auto","max_tokens":120}' | python3 -m json.tool
    ```

2. **Look for `tool_calls` in the response.** If the function call appears in `content` as text — even pretty text like `<tool_call>...</tool_call>` — the model **will fail the bench** and won't work cleanly in opencode. Move on.

3. **`finish_reason: tool_calls`** vs `finish_reason: stop` is the other tell. Stop means the model spoke text; tool_calls means it stopped specifically to call a function. Want the latter.

Verified-to-work base models for community fine-tuning where the chat template + tool-call shape both round-trip cleanly: vanilla Gemma 4 31B (proven by our 6/6 self-host result), Qwen 2.5 7B/14B Instruct, Ministral-8B-Instruct-2410, Mistral 7B v0.3. Stick to fine-tunes whose model card explicitly mentions OpenAI tool-call compatibility, or test before you trust.

### Speeding up local inference

The dual-GPU baseline above (Gemma-4-31B Q5_K_M, RTX 3080 + P100) decodes at **~12 tok/s**. That's why a bench task can take 5–10× longer than on warm NIM. Speedups, ranked by effort × payoff:

| Change | Effort | Expected speedup | Trade-off |
|---|---|---|---|
| **Drop the Pascal GPU, run on Ampere/Ada single-GPU** | trivial — remove `--tensor-split`, set `-ngl 99`, lower quant | **2–3×** | Need a model that fits one card. P100 (sm_60) has no FP16 tensor cores or flash-attention v2 → tensor parallel waits on it. |
| **Switch to a smaller code-tuned model** (`qwen2.5-coder-14b-instruct-q5_k_m`, `mistral-small-22b-instruct-q4_k_m`) | trivial — change `-m` | **3–4×** | Less generalist, but our bench shows 14B coders matching 31B on the standard tasks. |
| **Drop quant tier Q5_K_M → Q4_K_M → IQ4_XS** | trivial — re-download | **20–40%** | Q4_K_M is usually invisible quality loss; IQ4_XS shows on long reasoning. |
| **Speculative decoding** with a small draft model (`--draft -md gemma-2b-it.gguf`) | medium — add flags | **1.5–2.5×** | None functional. Needs same tokenizer family. |
| **Switch llama.cpp → exllamav2** (EXL2 quants) on Ampere+ | medium — new server, EXL2 weights | **1.3–1.7×** vs llama.cpp at same quant | No CPU offload, no Pascal support. |
| **Switch llama.cpp → vLLM with AWQ INT4** on Ampere+ | hard — different server | **3–5×** at high batch | No Pascal support; cold-start costs more VRAM. |
| **Replace P100 with a 24 GB Ampere card (RTX 3090 / 4090 / A5000)** | hardware | **4–6×** end-to-end | $500–1500. |

Concrete picks for the RTX 3080 + P100 baseline:

```bash
# Option 1: keep gemma-4-31b, harder quant, single 3080
hf download bartowski/google_gemma-4-31B-it-GGUF \
  --include google_gemma-4-31B-it-Q3_K_M.gguf \
  --local-dir ~/models/gemma4
# fits ~14 GB on the 3080 alone; expect ~25 tok/s
~/llama.cpp/build/bin/llama-server \
  -m ~/models/gemma4/google_gemma-4-31B-it-Q3_K_M.gguf \
  -ngl 99 -fa on --jinja -c 32768 \
  --host 0.0.0.0 --port 8085 -dev CUDA0

# Option 2: smaller code model, same single-GPU strategy
hf download bartowski/Qwen2.5-Coder-14B-Instruct-GGUF \
  --include Qwen2.5-Coder-14B-Instruct-Q5_K_M.gguf \
  --local-dir ~/models/qwen
# fits ~10 GB on the 3080 alone; expect ~40 tok/s, similar code quality
~/llama.cpp/build/bin/llama-server \
  -m ~/models/qwen/Qwen2.5-Coder-14B-Instruct-Q5_K_M.gguf \
  -ngl 99 -fa on --jinja -c 32768 \
  --host 0.0.0.0 --port 8085 -dev CUDA0
```

Either drops bench wall-time from ~21 min to ~5–7 min.

Knobs that don't help much:

- **Bumping `-b` / `-ub` prompt-eval batch size.** Already saturated at default 2048 for 31B-class. Helps if your prompt-eval is the bottleneck — ours is decode-bound.
- **`-ctk q4_0` (KV cache quant).** Saves ~30% KV VRAM but the speed delta is noise unless you're context-bound.
- **Pinning to one socket / NUMA tuning.** Inference is GPU-bound, CPU is mostly memcpy and tokenization.

### Option B — NVIDIA NIM container (paid NGC access)

Same OpenAI-compatible API, no quota, but requires an NGC subscription.

```bash
docker run --gpus all --shm-size=16GB -p 8000:8000 \
  -e NGC_API_KEY="$NGC_API_KEY" \
  nvcr.io/nim/meta/llama-3.3-70b-instruct:latest
```

Then edit `opencode.json`:

```json
"baseURL": "http://127.0.0.1:8000/v1"
```

### GPU sizing matrix (agentic-coding workloads)

What fits with ~4–8 GB held back for KV cache at 32 K context. Pick by VRAM, not by GPU model name — an A100-80 and an H100-80 fit the same things.

| VRAM | Example GPUs | Best agent model (single-GPU) | Format | Notes |
|---|---|---|---|---|
| 16–24 GB | RTX 3080 / 3090 / 4090 / 5070 Ti | `qwen2.5-coder-14b` or `llama-3.1-8b` | FP16 | 7 B–14 B easy; 32 B only at Q4 with tight KV |
| 36 GB | RTX 3080 + P100 (this README's setup) | **`gemma-4-31b-it`** | Q5_K_M | ~12 tok/s decode, 6/6 bench |
| 48 GB | RTX A6000 / L40 / L40S / 2× 3090 | `qwen3-coder-32b-instruct` or `gemma-4-31b-it` | BF16 / FP16 | sweet spot for code agents |
| 80 GB | A100-80 / H100 / H200 / B100 / B200 | **`llama-3.3-70b-instruct`** (FP8) or `gemma-4-31b-it` (BF16) | FP8 / BF16 | strongest single-GPU agent tier |
| 2× 80 GB | 2× H100 / H200 / B100 | `mistral-large-2` / `nemotron-3-super-120b-a12b` | FP8 | 120 B MoE class fits with room |
| 4× 80 GB | 4× H100 / H200 / B200 | `llama-3.1-405b` (FP8) | FP8 | dense 405 B fits 320 GB |
| 8× 80 GB | 8× H100 / H200 / GB200 | `kimi-k2.6` (1T MoE) / `nemotron-3-ultra-550b` | FP8 | the upstream NIM tier |

Rules of thumb:

- **Decode speed scales with active params, not total.** A 120 B MoE with 12 B active ≈ a dense 12 B for decode. Same wall-time, higher quality.
- **FP8 vs BF16 is roughly 2× density at ~99% quality** on Hopper/Blackwell. Use FP8 if your GPU supports it.
- **Q4/Q5_K_M GGUFs** are great for getting a model to fit a smaller card. Expect ~10–20 % quality drop vs FP16 on code agent tasks. For Q5_K_M specifically the loss is usually invisible.
- **MoE models (Mixtral, Qwen3, Nemotron-3-super, Kimi)** save decode tokens but still need full VRAM for all expert weights — don't size by active params alone.

### Reference architecture: 5-dev team on 4× RTX PRO 6000 Blackwell

Worked example for a small office. Replaces NIM dependency entirely.

**Critical: workstation RTX PRO 6000 Blackwell has no NVLink.** Inter-GPU traffic crosses PCIe Gen5 (~64 GB/s — about 30× slower than B-series NVLink). Don't tensor-parallel across cards. Run one model per card as independent replicas behind a router.

| GPU | Model | Format | VRAM | Role |
|---|---|---|---|---|
| Card 0 | `meta/llama-3.3-70b-instruct` | FP8 W8A8 (vLLM) | ~70 GB | opencode default — replica A |
| Card 1 | `meta/llama-3.3-70b-instruct` | FP8 W8A8 (vLLM) | ~70 GB | opencode default — replica B (load-balanced with A) |
| Card 2 | `qwen/qwen3-coder-32b-instruct` | BF16 (vLLM) | ~64 GB | dedicated to code-heavy tasks (large refactors, big diffs) |
| Card 3 | `gemma-4-31b-it` or `mistral-small-22b` | BF16 (vLLM) | ~60 GB | opencode `small_model` slot — summaries, tool routing, naming |

Per-replica throughput on RTX PRO 6000 Blackwell + vLLM (estimates from public benchmarks; verify with your own pilot):

| Model | Decode @ batch=1 | Aggregate @ batch=8 (continuous batching) |
|---|---|---|
| Llama-3.3-70B FP8 | ~70–90 tok/s | ~400–600 tok/s |
| Qwen3-Coder-32B BF16 | ~80–110 tok/s | ~600–900 tok/s |
| Gemma-4-31B BF16 | ~120–160 tok/s | ~700–1000 tok/s |

For 5 devs with bursty agent traffic, 2 Llama-70B replicas alone give ~1000 tok/s aggregate — roughly 20× headroom. The code and fast cards are bonus capacity, not load-bearing.

**Routing**: put LiteLLM in front of the four vLLM endpoints; opencode talks to one base URL. Two `llama-70b` entries with the same `model_name` make LiteLLM round-robin between Cards 0 and 1.

```yaml
# litellm_config.yaml
model_list:
  - model_name: llama-70b
    litellm_params: { model: openai/meta-llama-3.3-70b-instruct, api_base: http://card0:8001/v1 }
  - model_name: llama-70b
    litellm_params: { model: openai/meta-llama-3.3-70b-instruct, api_base: http://card1:8001/v1 }
  - model_name: qwen-coder-32b
    litellm_params: { model: openai/qwen3-coder-32b-instruct, api_base: http://card2:8001/v1 }
  - model_name: gemma-31b-fast
    litellm_params: { model: openai/gemma-4-31b-it, api_base: http://card3:8001/v1 }
```

**Supporting infrastructure** (easy to underspec around the GPUs):

| Item | Requirement |
|---|---|
| CPU + board | 4× PCIe Gen5 x16 = 64 lanes from CPU (Threadripper Pro 7975WX or EPYC 7373X class) |
| RAM | 256 GB DDR5 ECC |
| PSU | 4× 600 W cards → 3000 W titanium, or 2× 1600 W |
| Chassis | 4U workstation/server (e.g. ASUS ESC8000A-E12, Supermicro AS-4125GS-TNRT) |
| Storage | 4 TB NVMe Gen4 + bulk HDD for model cache |
| Power circuit | 240 V dedicated, ~3.5 kW sustained under load |
| Cooling | Server closet or dedicated AC — 4 of these heats a closed office noticeably |

**Pilot first.** RTX PRO 6000 Blackwell launched in 2025; vLLM and TensorRT-LLM Blackwell-specific kernel paths (FP8 / NVFP8 / FP4) are mature as of mid-2026 but still seeing edge-case fixes. Buy one card, validate your real workload runs cleanly under vLLM with FP8 weights, then commit to the remaining three.

**When this config stops being right**:

- **10–15 devs**: same cards, add a 5th (or run 2 replicas per card with smaller models). Replicas scale linearly.
- **20+ devs / batch CI workloads**: jump tier to B100 PCIe. HBM3e at 8 TB/s (vs RTX PRO's 1.8 TB/s GDDR7) starts to matter under sustained high-concurrency throughput.
- **Need 200 K+ context routinely**: still possible on 96 GB per card, but KV budget tightens — drop Qwen3-Coder-32B to AWQ INT4 to claw back KV space.

## Want to collaborate?

If you're setting nimcode up for a team, integrating it with an internal LLM gateway, building custom skill libraries, or just want a hand getting it running on your stack — I'm keen to help.

Drop me a line at **rickesh.t.n@gmail.com** with what you're working on.

## Troubleshooting

[`docs/troubleshooting.md`](docs/troubleshooting.md) covers: `EACCES` on global npm install, `nimcode: command not found`, 401/429/503 from NIM, broken tool-call models, and resetting everything.

## Uninstall

```bash
./uninstall.sh          # removes ~/.config/nim-code + ~/.local/bin/nimcode
npm rm -g opencode-ai   # remove the underlying CLI (optional)
rm -f ~/.nvidia_api_key # forget the key file
```

## Credits

- [opencode](https://opencode.ai) — the upstream CLI doing the real work. nim-code is config + glue.
- [NVIDIA NIM](https://build.nvidia.com) — hosted model endpoint.
- [Moonshot AI](https://moonshot.ai) — Kimi K2.6.

## Contributing

PRs welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md). Static checks (shellcheck + Python syntax + JSON schema) run in CI.

## License

MIT — see [LICENSE](LICENSE).
