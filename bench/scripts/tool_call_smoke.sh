#!/usr/bin/env bash
# Verifies a model actually emits OpenAI-shaped tool_calls (or content that
# the local normalizer can rewrite into tool_calls).
#
# Defaults probe the NVIDIA NIM upstream. Override for local Ollama:
#   ENDPOINT=http://127.0.0.1:11434/v1/chat/completions \
#   API_KEY=ollama \
#   bash tool_call_smoke.sh hf.co/<repo>:Q4_K_M
#
# Pipes the raw response through the normalizer so wrapped tool calls
# (composer2.5/fable5 pycall, qwen tag_json, etc) are detected as PASS too.
set -uo pipefail

MODEL="${1:-meta/llama-3.3-70b-instruct}"
ENDPOINT="${ENDPOINT:-https://integrate.api.nvidia.com/v1/chat/completions}"
API_KEY="${API_KEY:-${NVIDIA_API_KEY:-}}"

curl_args=( -sS "$ENDPOINT" -H "Content-Type: application/json" )
if [ -n "$API_KEY" ]; then
  curl_args+=( -H "Authorization: Bearer $API_KEY" )
fi

# When hitting a localhost endpoint (Ollama default), embed the tool schema
# into the system prompt rather than the `tools` field, because community
# GGUFs lack a tool-aware Modelfile and ollama rejects requests otherwise.
# The normalizer then rewrites the wrapped call out of message.content.
case "$ENDPOINT" in
  *127.0.0.1*|*localhost*|*0.0.0.0*) LOCAL=1 ;;
  *) LOCAL=0 ;;
esac

if [ "$LOCAL" = "1" ]; then
  payload="{
    \"model\": \"$MODEL\",
    \"messages\": [
      {\"role\":\"system\",\"content\":\"You are a tool-using agent. When asked about weather, call get_weather. Emit the call as <tool_call>get_weather(city=\\\"...\\\")</tool_call> OR <tool_call>{\\\"name\\\":\\\"get_weather\\\",\\\"arguments\\\":{\\\"city\\\":\\\"...\\\"}}</tool_call>. Tool spec: {\\\"name\\\":\\\"get_weather\\\",\\\"parameters\\\":{\\\"type\\\":\\\"object\\\",\\\"properties\\\":{\\\"city\\\":{\\\"type\\\":\\\"string\\\"}},\\\"required\\\":[\\\"city\\\"]}}\"},
      {\"role\":\"user\",\"content\":\"What is the weather in Tokyo? Call the tool.\"}
    ],
    \"max_tokens\": 512,
    \"temperature\": 0.2
  }"
else
  payload="{
    \"model\": \"$MODEL\",
    \"messages\": [
      {\"role\":\"system\",\"content\":\"You are a tool-using agent. Always call the provided tool when asked about weather.\"},
      {\"role\":\"user\",\"content\":\"What is the weather in Tokyo?\"}
    ],
    \"tools\": [{
      \"type\":\"function\",
      \"function\":{
        \"name\":\"get_weather\",
        \"description\":\"Get current weather for a city\",
        \"parameters\":{
          \"type\":\"object\",
          \"properties\":{\"city\":{\"type\":\"string\"}},
          \"required\":[\"city\"]
        }
      }
    }],
    \"tool_choice\":\"auto\",
    \"max_tokens\": 512
  }"
fi

curl "${curl_args[@]}" -d "$payload" | python3 -c '
import json, os, sys, pathlib
# Resolve normalizer from the same dir as this script.
script_dir = pathlib.Path(os.environ.get("SMOKE_SCRIPT_DIR", "")).resolve()
if not script_dir.exists():
    script_dir = pathlib.Path(__file__).resolve().parent if "__file__" in dir() else pathlib.Path.cwd()
sys.path.insert(0, str(script_dir))
try:
    from tool_call_normalizer import normalize_response
except Exception:
    normalize_response = lambda b: b

raw = sys.stdin.buffer.read()
norm = normalize_response(raw)
r = json.loads(norm)
msg = r["choices"][0]["message"]
tc = msg.get("tool_calls")
if not tc:
    print("FAIL: no tool_calls, normalizer found no wrapper either")
    print("       raw content:", (msg.get("content","") or "")[:240])
    sys.exit(1)
call = tc[0]["function"]
print("OK  model=", r.get("model"))
print("    fn:", call["name"])
print("    args:", call["arguments"])
print("    via:", "normalizer" if norm is not raw else "native")
'
