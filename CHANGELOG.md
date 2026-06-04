# Changelog

## 0.1.0 — initial public release

- `install.sh` one-shot installer: detects Node ≥20 + npm, installs `opencode-ai` globally, drops a NIM-preconfigured `opencode.json` into `~/.config/nim-code/`, resolves an `nvapi-...` key (env → `~/.nvidia_api_key` → previous install → interactive prompt), validates the key against the live NIM `/chat/completions` endpoint, writes a `nimcode` launcher to `~/.local/bin/`.
- Default model: `moonshotai/kimi-k2.6` (best on internal coding-agent stress suite — see `docs/benchmarks.md`).
- Provider catalog in `opencode.json`: Kimi K2.6, Qwen3-Coder 480B, Qwen3.5 122B, Nemotron-3 Super 120B, Llama 3.3 70B, Llama 3.1 8B (small-model role).
- Benchmark harness under `bench/` — headless OpenAI-tool-call agent + six pass/fail coding tasks (LRU, toposort, rate limiter, B-tree, mini-grep, god-class refactor).
- Optional telemetry (Cloudflare Worker + D1, see `telemetry/`). Opt-out via `NIMCODE_NO_TELEMETRY=1` or `touch ~/.config/nim-code/no-telemetry`. Sends only: random install UUID, event name, version, OS, arch. **Never sends the API key, hostname, username, or paths.**
