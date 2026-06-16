# Tool-call output formats — survey + per-model profiles

When opencode (or the bench harness) sends a chat completion with a `tools` array, it expects the response to come back with `choices[0].message.tool_calls[]` populated and `finish_reason: "tool_calls"` — the OpenAI structured tool-call shape. The agent loop dispatches on that field.

In practice models / backends frequently fail to produce that shape. The function call still appears in the response, but as **text inside `message.content`** in one of several non-standard wrappers. The harness then logs `"no tool_calls — ending loop"` and the task fails at turn 1, regardless of whether the model would otherwise have solved it.

This document catalogs the formats we have observed in practice and maps each model to the parsing profile used by [`tool_call_normalizer.py`](../../gemma4_wClaude/tool_call_normalizer.py) (in the sibling project dir). The normalizer is a thin sidecar that sits between the bench harness / opencode and the actual backend, detects the textual tool-call wrapper, parses it, and rewrites the response to the OpenAI structured shape.

## Observed wrappers

Each wrapper below is something we have seen in a real response on this bench. The catalog is conservative — patterns are added only after we have a verbatim sample.

| Wrapper | Example body | Parser strategy |
|---|---|---|
| **OpenAI native** | `{"tool_calls": [{"type":"function","function":{"name":"X","arguments":"…"}}]}` | `native` (no rewrite) |
| **Markdown JSON fence** | ```` ```json\n{"name": "X", "arguments": {...}}\n``` ```` | `md_fence` |
| **Bare JSON** | `{"name": "X", "arguments": {...}}` at the head of `content` | `bare_json` |
| **`<function-calls>` JSON** | `<function-calls>{"name":"X","arguments":{...}}</function-calls>` | `tag_json` |
| **`<function_call>` JSON** | `<function_call>{"name":"X","arguments":{...}}</function_call>` | `tag_json` |
| **`<tool_call>` JSON** | `<tool_call>{"name":"X","arguments":{...}}</tool_call>` (chatml / Hermes / Functionary) | `tag_json` |
| **`<tools>` JSON** | `<tools>{"name":"X","arguments":{...}}</tools>` | `tag_json` |
| **`<tools>` JSON-array** | `<tools>[{...}, {...}]</tools>` | `tag_json` |
| **`<TOOLCALL>` JSON-array** | `<TOOLCALL>[{"name":"X","arguments":{...}}]</TOOLCALL>` (nemotron-49b) | `tag_array` |
| **`<tool_call>` Python call** | `<tool_call>X(path="…", content="…")</tool_call>` (composer / fable fine-tunes) | `tag_pycall` |
| **Kimi sentinel leak (v0.2 NIM bug)** | `…assistant text… <\|tool_call_end\|> <\|tool_calls_section_end\|>` | currently *unparseable* — see notes |

## Per-model profiles

Profiles are matched against the response's `model` field by regex. First match wins. Unknown models fall back to `DEFAULT_PROFILE` (try all strategies in turn).

| Model pattern | Backend | Profile order | Source |
|---|---|---|---|
| `^Qwen2\.5-Coder.*Instruct` | llama.cpp (`peg-native`) | `md_fence` → `bare_json` → `tag_json` | bench v0.2 (35 rewrites across 6 tasks) |
| `composer2?\.?5` / `fable[-_]?5` | llama.cpp | `tag_pycall` → `tag_json` → `md_fence` → `bare_json` | bench v0.2 (12B coder fine-tune) |
| `nemotron-super-49b` | NIM upstream | `tag_array` → `tag_json` | bench v0.1 (0/6, format catalogued for completeness) |
| `moonshotai/kimi-` | NIM upstream | `native` | bench v0.2 (mostly clean; one truncation-related failure) |
| `^gemma-4.*it\b` (vanilla) | llama.cpp `peg-gemma4` | `native` | bench v0.2 (6/6 self-host) |
| `^(meta/\|mistralai/\|nvidia/\|microsoft/\|google/)` | NIM upstream | `native` | bench v0.2 |
| anything else | — | try-all default | safe fallback |

## Strategies

Strategies are independent extractors invoked by name. Each receives the response's `content` string and returns either a tuple `(start, end, [(name, args), ...])` indicating the chunk to strip and the calls to inject, or `None` if it could not match.

- **`native`** — assert no rewrite needed. Returns `None` immediately. Use for models / backends that already speak OpenAI tool_calls.
- **`md_fence`** — `re.findall` for ```` ```(?:json)?\n…\n``` ```` blocks, attempt `json.loads` on the inner payload, accept if it looks like `{name, arguments}`.
- **`bare_json`** — walk `content` for balanced `{...}` blocks (proper brace-counting that respects strings), `json.loads` each, accept the first that looks like `{name, arguments}`.
- **`tag_json`** — try a small list of named-tag wrappers (`<function-calls>`, `<function_call>`, `<tool_call>`, `<tools>`, `<tool_calls>`), parse the JSON body.
- **`tag_array`** — `<TOOLCALL>[…]</TOOLCALL>`, parse as a JSON array of calls.
- **`tag_pycall`** — `<tool_call>fn(arg=val, ...)</tool_call>`, parse the Python-syntax kwargs with `ast.literal_eval` semantics into a JSON arguments dict.

## How to add a new profile

1. Spin up `llama-server` (or whatever backend) loading the new model.
2. Send the tool-call probe from the README's "Trying community fine-tunes" subsection.
3. Look at the `content` field of the response. If `tool_calls` is already populated, the profile is `native`; you're done.
4. Otherwise identify the wrapper visually:
   - Does the JSON appear inside a ```` ```json ``` ```` fence? `md_fence`.
   - Is it bare JSON at the start? `bare_json`.
   - Wrapped in some `<tag>{...}</tag>`? Add a regex to `_strat_tag_json` (or a sibling) and reference it.
   - Is the function call written in Python `fn(arg=val)` form? `tag_pycall`.
5. Add a `(re.compile(r"…"), [strategies, …])` entry to `MODEL_PROFILES` in `tool_call_normalizer.py`. Earlier entries take precedence over later ones.
6. Run the bench against the new model and confirm the count of `[normalizer] rewrote …` log lines roughly matches the number of turns the model would normally attempt to call a tool. If the rewrite count is low, the strategy isn't matching every response — add another sample's pattern.

## Kimi sentinel leak (v0.2 NIM-side regression)

This is the one observed format we do **not** currently parse, because it isn't actually a tool call in disguise — it looks like the upstream NIM serializer dropping its sentinel-end markers into the streamed content without a corresponding call body to recover. We saw it once on `moonshotai/kimi-k2.6` for `05_minigrep` in v0.2; subsequent NIM bench runs of the same model showed it less frequently. Treating it as "model emitted no tool_calls" and ending the loop is the correct fall-back. Documenting here for completeness.

## Backend recommendation

llama.cpp's tool-call parser (`peg-*` family) only translates output back to OpenAI shape when the model's chat template is in its known set. Anything else falls back to `peg-native` (passthrough) and you need this normalizer. **vLLM** has explicit per-model tool-call parsers for Qwen 2.5, Hermes, Functionary, etc. and emits clean `tool_calls[]` natively. If you are running anything beyond vanilla Gemma 4 locally, vLLM is the cleaner long-term answer; the normalizer is the right tool while staying on llama.cpp.
