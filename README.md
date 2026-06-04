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

## Quick start

### One-line install (recommended for new users)

```bash
curl -fsSL https://raw.githubusercontent.com/natkal-coder/nim-code/main/install.sh | bash
nimcode
```

That's it. The installer downloads its own `opencode.json` from the repo on the fly. Needs Node ≥20 and an `nvapi-...` key in `~/.nvidia_api_key` or `$NVIDIA_API_KEY` (else it'll prompt — but `curl | bash` has no tty, so save the key first):

```bash
# Save your key once, then run the one-liner
printf '%s\n' 'nvapi-XXXXXXXX...' > ~/.nvidia_api_key
chmod 600 ~/.nvidia_api_key
curl -fsSL https://raw.githubusercontent.com/natkal-coder/nim-code/main/install.sh | bash
```

### Or clone + run

```bash
git clone https://github.com/natkal-coder/nim-code && cd nim-code
./install.sh        # interactive prompt available
nimcode
```

No Docker, no Python venv, no Node version manager. Plain bash + Node ≥20.

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
| **`moonshotai/kimi-k2.6`** | **default** — 1T MoE, fastest tool calls | **6 / 6** |
| `qwen/qwen3-coder-480b-a35b-instruct` | strongest coder; rate-limited on free tier | 2 / 3 completed |
| `qwen/qwen3.5-122b-a10b` | general-purpose alt | not yet benched |
| `nvidia/nemotron-3-super-120b-a12b` | Mamba-Transformer hybrid, 200k ctx | not yet benched |
| `meta/llama-3.3-70b-instruct` | stable fallback | 3 / 6 |
| `meta/llama-3.1-8b-instruct` | small/fast (opencode `small_model` slot) | n/a |

Methodology + per-task results: [`docs/benchmarks.md`](docs/benchmarks.md).

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
