# Troubleshooting

## `npm i -g opencode-ai` fails with EACCES

Your global npm prefix is root-owned. Fix:

```bash
mkdir -p ~/.npm-global
npm config set prefix ~/.npm-global
export PATH="$HOME/.npm-global/bin:$PATH"  # add to ~/.bashrc or ~/.zshrc
./install.sh
```

## `nimcode: command not found`

`~/.local/bin` is not on your PATH. The installer warns about this. Add:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

to `~/.bashrc` (bash) or `~/.zshrc` (zsh), then `exec $SHELL`.

## `auth rejected (401)` during install

Your key is wrong, expired, or revoked. Get a new one at https://build.nvidia.com → any model → "Get API Key". Save it to `~/.nvidia_api_key`, then `./install.sh --reset`.

## `HTTP 429 Too Many Requests` during a session

NIM free-tier rate limit (40 RPM per key). Options:
1. Wait a minute and continue.
2. Use a smaller model: `/models` → switch to `meta/llama-3.1-8b-instruct`.
3. Move to a paid NIM endpoint or self-hosted NIM container.

## `HTTP 503 ResourceExhausted`

Server-side capacity, not your quota. Some models (notably Qwen3-Coder 480B) hit this regularly on free tier. Switch model and retry.

## Some model in `/models` always errors

Run the tool-call smoke test:

```bash
. ~/.config/nim-code/env
bench/scripts/tool_call_smoke.sh <model_id>
```

If it prints `FAIL: no tool_calls` or `TOOLCALL_NO`, the model on NIM doesn't emit OpenAI-shaped tool calls. Drop it from `~/.config/nim-code/opencode.json`.

## Resetting everything

```bash
./uninstall.sh                          # removes ~/.config/nim-code + ~/.local/bin/nimcode
rm -f ~/.nvidia_api_key                 # forget the key file
npm rm -g opencode-ai                   # remove the underlying CLI
```

## Opting out of telemetry

Pick any one:

```bash
# permanent, system-wide for your user
touch ~/.config/nim-code/no-telemetry

# permanent, in your shell rc
echo 'export NIMCODE_NO_TELEMETRY=1' >> ~/.bashrc

# verify by checking the install_id file is the only thing in the dir that grew
ls -la ~/.config/nim-code/
```
