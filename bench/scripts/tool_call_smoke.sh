#!/usr/bin/env bash
# Verifies the chosen NIM model actually emits OpenAI-shaped tool_calls.
# Many NIM models advertise tools support but emit malformed deltas under streaming.
# Run this before trusting a model in the agent loop.
set -euo pipefail

MODEL="${1:-meta/llama-3.3-70b-instruct}"
: "${NVIDIA_API_KEY:?set NVIDIA_API_KEY}"

curl -sS https://integrate.api.nvidia.com/v1/chat/completions \
  -H "Authorization: Bearer $NVIDIA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$MODEL\",
    \"messages\": [
      {\"role\":\"system\",\"content\":\"You are a tool-using agent. Always call the provided tool when asked about weather.\"},
      {\"role\":\"user\",\"content\":\"What's the weather in Tokyo?\"}
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
    \"max_tokens\": 256
  }" | python3 -c '
import json,sys
r=json.load(sys.stdin)
msg=r["choices"][0]["message"]
tc=msg.get("tool_calls")
if not tc:
  print("FAIL: no tool_calls. raw content:", msg.get("content","")[:200]); sys.exit(1)
call=tc[0]["function"]
print("OK model=", r.get("model"))
print("  fn:", call["name"])
print("  args:", call["arguments"])
'
