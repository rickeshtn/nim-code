"""
Tool-call shape normalizer.

Sits between an OpenAI-compatible client (opencode, bench harness) and a
llama-server (or any backend) that emits tool calls as TEXT inside the
assistant message content instead of as the structured `tool_calls[]` field.
This is llama.cpp's behavior for models where its parser falls back to
`peg-native` passthrough — Qwen 2.5, some community fine-tunes, etc.

Detected wrappers (case-insensitive on the tag, multiline body):

  <function-calls>{ "name": "...", "arguments": {...} }</function-calls>   (Qwen 2.5 GGUF)
  <function_call>{ "name": "...", "arguments": {...} }</function_call>
  <tool_call>{ "name": "...", "arguments": {...} }</tool_call>             (chatml/Hermes)
  <tool_call>fn_name(arg1=val1, arg2=val2)</tool_call>                     (Composer/Fable fine-tunes)
  <TOOLCALL>[{"name": "...", "arguments": {...}}]</TOOLCALL>                (nemotron-49b)

On match, the proxy:
  1. Parses out (name, arguments) from the text.
  2. Removes the text from the message content.
  3. Inserts the structured `tool_calls[]` field.
  4. Forces finish_reason = "tool_calls".

Other paths and non-matching responses pass through untouched.

Usage:
    UPSTREAM=http://127.0.0.1:8087 PROXY_PORT=8085 \
        python3 tool_call_normalizer.py
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


PROXY_PORT = int(os.environ.get("PROXY_PORT", "8085"))
UPSTREAM = os.environ.get("UPSTREAM", "http://127.0.0.1:8087").rstrip("/")


# --- model -> profile registry ---
# Each profile is a list of strategy names that will be tried in order against
# the assistant message content. Defaults to the "all" pipeline for unknown
# models. Add or refine entries as new formats are observed.
#
# Strategy names map to functions further down:
#   "native"     — model already returns OpenAI tool_calls[]; skip parsing
#   "tag_json"   — <function-calls> / <tools> / <tool_call> wrapping JSON
#   "tag_array"  — <TOOLCALL>[...]</TOOLCALL>
#   "tag_pycall" — <tool_call>fn(arg=val)</tool_call>
#   "md_fence"   — ```json {...} ``` markdown fence
#   "bare_json"  — leading {...} balanced JSON with name + arguments
#
# Reference catalog: docs/tool_call_formats.md (in NIM_claude_code repo).

MODEL_PROFILES = [
    # (model-name regex, profile list)
    (re.compile(r"^Qwen2\.5-Coder.*Instruct", re.I), ["md_fence", "bare_json", "tag_json"]),
    # Gemma-4 fable5/composer2.5 fine-tunes: v2 (agentic/tau2) emits the
    # Gemma-4 NATIVE tool format when fronted by Ollama without --jinja:
    #   <|tool_call>call:fn{k:<|"|>v<|"|>}<tool_call|>
    # v1 (coder) sometimes emits the plainer <tool_call>fn(args)</tool_call>.
    # Try gemma4_native first; fall back to pycall/json wrappers.
    (re.compile(r"gemma-?4.*(fable|composer|agentic|tau2)", re.I),
     ["gemma4_native", "tag_pycall", "tag_json", "md_fence", "bare_json"]),
    (re.compile(r"composer2?\.?5|fable[-_]?5", re.I), ["tag_pycall", "tag_json", "md_fence", "bare_json"]),
    # Qwythos / Qwen3.5: Qwen-style tag_json + md_fence per the model card.
    (re.compile(r"qwythos|qwen3\.5", re.I), ["tag_json", "md_fence", "bare_json"]),
    (re.compile(r"nemotron-super-49b", re.I), ["tag_array", "tag_json"]),
    (re.compile(r"moonshotai/kimi", re.I), ["native"]),  # NIM returns OpenAI shape; v0.2 had a separate truncation bug
    (re.compile(r"^(google_)?gemma-4.*it\b", re.I), ["native"]),  # llama.cpp's peg-gemma4 path already returns tool_calls
    (re.compile(r"^(meta/|mistralai/|nvidia/|microsoft/|google/)", re.I), ["native"]),  # canonical NIM upstream
]
DEFAULT_PROFILE = ["gemma4_native", "tag_json", "tag_array", "tag_pycall", "md_fence", "bare_json"]


# --- pattern set: each entry is (compiled regex, parse fn -> [(name, args_dict), ...]) ---

def _parse_json_obj(match):
    try:
        obj = json.loads(match.group(1))
    except Exception:
        return []
    return [(obj["name"], obj.get("arguments", {}))]


def _parse_json_array(match):
    try:
        arr = json.loads(match.group(1))
    except Exception:
        return []
    out = []
    for c in arr:
        if "name" in c:
            out.append((c["name"], c.get("arguments", {})))
    return out


_KV_PAIR = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[^,)\s][^,)]*)')


def _parse_py_call(match):
    name = match.group(1)
    args_blob = match.group(2)
    args = {}
    for k, v in _KV_PAIR.findall(args_blob):
        v = v.strip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            try:
                args[k] = json.loads('"' + v[1:-1].replace('"', '\\"') + '"')
            except Exception:
                args[k] = v[1:-1]
        else:
            # try int/float/bool/json
            try:
                args[k] = json.loads(v)
            except Exception:
                args[k] = v
    return [(name, args)] if name else []


PATTERNS = [
    # JSON-body wrapped in various tags
    (re.compile(r'<function[-_]calls?>\s*(\{[^<]*?\})\s*</function[-_]calls?>', re.S | re.I), _parse_json_obj),
    (re.compile(r'<tool_calls?>\s*(\{[^<]*?\})\s*</tool_calls?>', re.S | re.I), _parse_json_obj),
    # `<function>` (singular) — Qwen 2.5 via vLLM/hermes occasionally drops this
    (re.compile(r'<function>\s*(\{[^<]*?\})\s*</function>', re.S | re.I), _parse_json_obj),
    # Qwen 2.5 also emits this one (despite having no `<tools>` in its own template)
    (re.compile(r'<tools?>\s*(\{[^<]*?\})\s*</tools?>', re.S | re.I), _parse_json_obj),
    (re.compile(r'<tools?>\s*(\[[^<]*?\])\s*</tools?>', re.S | re.I), _parse_json_array),
    (re.compile(r'<TOOLCALL>\s*(\[[^<]*?\])\s*</TOOLCALL>', re.S), _parse_json_array),
    (re.compile(r'<TOOLCALL>\s*(\{[^<]*?\})\s*</TOOLCALL>', re.S), _parse_json_obj),
    # Python-call body
    (re.compile(r'<tool_call>\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)\s*</tool_call>', re.S), _parse_py_call),
]


_MD_FENCE = re.compile(r"```(?:json|JSON)?\s*\n?(.*?)\n?```", re.S)


def _balanced_json_blocks(s: str):
    """Yield (start, end, parsed_obj) for every balanced {...} JSON block in s
    that successfully parses. Skips strings inside the JSON correctly."""
    i, n = 0, len(s)
    while i < n:
        if s[i] != "{":
            i += 1
            continue
        # find balanced closing brace, respecting strings
        depth = 0
        j = i
        in_str = False
        esc = False
        while j < n:
            c = s[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            obj = json.loads(s[i:j + 1])
                            yield (i, j + 1, obj)
                        except Exception:
                            pass
                        break
            j += 1
        i = j + 1


def _strat_tag_json(content):
    """Tagged-JSON wrappers — <function-calls>, <tools>, <tool_call> with JSON body."""
    for regex, parse_fn in PATTERNS:
        m = regex.search(content)
        if not m:
            continue
        calls = parse_fn(m)
        if calls:
            return (m.start(), m.end(), calls)
    return None


def _strat_tag_array(content):
    """<TOOLCALL>[...]</TOOLCALL> — nemotron-49b style."""
    for regex in [
        re.compile(r'<TOOLCALL>\s*(\[[^<]*?\])\s*</TOOLCALL>', re.S),
        re.compile(r'<TOOLCALL>\s*(\{[^<]*?\})\s*</TOOLCALL>', re.S),
    ]:
        m = regex.search(content)
        if not m:
            continue
        parser = _parse_json_array if m.group(1).lstrip().startswith("[") else _parse_json_obj
        calls = parser(m)
        if calls:
            return (m.start(), m.end(), calls)
    return None


def _strat_tag_pycall(content):
    """<tool_call>fn(arg=val, ...)</tool_call> — composer/fable fine-tunes."""
    regex = re.compile(r'<tool_call>\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)\s*</tool_call>', re.S)
    m = regex.search(content)
    if not m:
        return None
    calls = _parse_py_call(m)
    if calls:
        return (m.start(), m.end(), calls)
    return None


def _strat_md_fence(content):
    """```json {...} ``` — Qwen Coder default for most turns."""
    for fence in _MD_FENCE.finditer(content):
        inner = fence.group(1).strip()
        try:
            obj = json.loads(inner)
        except Exception:
            objs = list(_balanced_json_blocks(inner))
            if not objs:
                continue
            _, _, obj = objs[0]
        calls = _normalize_call_obj(obj)
        if calls:
            return (fence.start(), fence.end(), calls)
    return None


def _strat_bare_json(content):
    """Any balanced {...} that parses to {name, arguments} — Qwen alternate."""
    for (s_idx, e_idx, obj) in _balanced_json_blocks(content):
        calls = _normalize_call_obj(obj)
        if calls:
            return (s_idx, e_idx, calls)
    return None


# Gemma-4 native tool-call wire format (as it leaks when --jinja is OFF):
#   <|tool_call>call:fn_name{key:<|"|>val<|"|>, key2:<|"|>val2<|"|>}<tool_call|>
# - <|"|> is the Gemma-4 pseudo-quote token; strip it to recover real strings.
# - Body keys are bare identifiers; values may be quoted strings, numbers, or
#   simple JSON literals (true/false/null).
_GEMMA4_TOOLCALL = re.compile(
    r'<\|tool_call>\s*call:\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\{(.*?)\}\s*<tool_call\|>',
    re.S,
)
_GEMMA4_PSEUDO_QUOTE = re.compile(r'<\|"\|>')


def _parse_gemma4_native(match):
    name = match.group(1)
    body = _GEMMA4_PSEUDO_QUOTE.sub('"', match.group(2))
    # body now reads like:  key:"val", key2:"val2", flag:true, n:42
    pair_re = re.compile(
        r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*'
        r'("(?:\\.|[^"\\])*"|true|false|null|-?\d+(?:\.\d+)?|[^,}\s][^,}]*)',
        re.S,
    )
    args = {}
    for k, v in pair_re.findall(body):
        v = v.strip()
        try:
            args[k] = json.loads(v)
        except Exception:
            args[k] = v.strip('"')
    return [(name, args)] if name else []


def _strat_gemma4_native(content):
    """<|tool_call>call:fn{k:<|"|>v<|"|>}<tool_call|> — Gemma-4 native protocol
    that leaks when Ollama serves the model without --jinja template parsing."""
    m = _GEMMA4_TOOLCALL.search(content)
    if not m:
        return None
    calls = _parse_gemma4_native(m)
    if calls:
        return (m.start(), m.end(), calls)
    return None


STRATEGIES = {
    "tag_json": _strat_tag_json,
    "tag_array": _strat_tag_array,
    "tag_pycall": _strat_tag_pycall,
    "md_fence": _strat_md_fence,
    "bare_json": _strat_bare_json,
    "gemma4_native": _strat_gemma4_native,
}


def _profile_for(model_name: str):
    if not model_name:
        return DEFAULT_PROFILE
    for regex, profile in MODEL_PROFILES:
        if regex.search(model_name):
            return profile
    return DEFAULT_PROFILE


def _extract_calls_from_text(content: str, model_name: str = ""):
    """Multi-strategy extraction. Dispatches to profile-appropriate strategy
    list for the model. Returns (start, end, [(name, args), ...]) or None."""
    profile = _profile_for(model_name)
    for strat_name in profile:
        if strat_name == "native":
            return None  # by contract: this model never needs parsing
        fn = STRATEGIES.get(strat_name)
        if fn is None:
            continue
        out = fn(content)
        if out:
            return out
    return None


def _normalize_call_obj(obj):
    """Accept a parsed JSON object and return [(name, args), ...] if it looks
    like one tool call or an array of them. Returns [] otherwise."""
    if isinstance(obj, dict) and "name" in obj and "arguments" in obj:
        return [(obj["name"], obj["arguments"])]
    if isinstance(obj, list) and obj:
        out = []
        for c in obj:
            if isinstance(c, dict) and "name" in c and "arguments" in c:
                out.append((c["name"], c["arguments"]))
        return out
    return []


def normalize_response(body_bytes: bytes) -> bytes:
    """If the chat response stuffed a tool call into content as text, rewrite it
    to the structured OpenAI tool_calls field. Pass-through on no match."""
    try:
        r = json.loads(body_bytes)
    except Exception:
        return body_bytes
    try:
        choices = r.get("choices") or []
        if not choices:
            return body_bytes
        msg = choices[0].get("message") or {}
        content = msg.get("content") or ""
        if not content or msg.get("tool_calls"):
            return body_bytes

        # Determine which model this response is for so we pick the right
        # profile. The model id is in the top-level "model" field of the
        # OpenAI response.
        model_name = r.get("model", "") or ""
        extracted = _extract_calls_from_text(content, model_name)
        if not extracted:
            return body_bytes
        start, end, calls = extracted
        tool_calls = []
        for i, (name, args) in enumerate(calls):
            tool_calls.append({
                "id": f"call_norm_{abs(hash(content) + i) % 10**12:012d}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(args) if isinstance(args, dict) else str(args),
                },
            })
        new_content = (content[:start] + content[end:]).strip()
        msg["content"] = new_content
        msg["tool_calls"] = tool_calls
        choices[0]["finish_reason"] = "tool_calls"
        sys.stderr.write(
            f"[normalizer] rewrote {len(tool_calls)} tool_call(s) "
            f"({calls[0][0]!r}) — first 60 char content was: "
            f"{content[:60]!r}\n"
        )
        sys.stderr.flush()
        return json.dumps(r).encode("utf-8")
    except Exception as e:
        sys.stderr.write(f"[normalizer] parse skipped: {e}\n")
        sys.stderr.flush()
        return body_bytes


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # quieter; the normalize_response logs what matters

    def _forward(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        url = UPSTREAM + self.path
        req = urllib.request.Request(url, data=body or None, method=self.command)
        for k, v in self.headers.items():
            if k.lower() in ("host", "content-length", "connection", "transfer-encoding"):
                continue
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                rb = resp.read()
                rh = dict(resp.getheaders())
                status = resp.getcode()
        except urllib.error.HTTPError as e:
            rb = e.read()
            rh = dict(e.headers)
            status = e.code
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            err = json.dumps({"error": f"upstream: {e}"}).encode()
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)
            return
        # only rewrite chat.completions JSON
        if self.command == "POST" and self.path.endswith("/chat/completions"):
            ct = rh.get("Content-Type") or rh.get("content-type") or ""
            if "json" in ct:
                rb = normalize_response(rb)
        # Always recompute content-length from final body. Header dict is
        # case-sensitive — drop ANY existing Content-Length variant so we
        # don't emit the duplicate that breaks JSON parsing downstream.
        rh = {k: v for k, v in rh.items() if k.lower() != "content-length"}
        rh["Content-Length"] = str(len(rb))
        self.send_response(status)
        for k, v in rh.items():
            if k.lower() in ("transfer-encoding", "connection"):
                continue
            self.send_header(k, v)
        self.end_headers()
        if rb:
            self.wfile.write(rb)

    do_GET = do_POST = do_OPTIONS = do_PUT = do_DELETE = _forward


def main():
    print(f"[normalizer] listening on :{PROXY_PORT} -> {UPSTREAM}", flush=True)
    s = ThreadingHTTPServer(("0.0.0.0", PROXY_PORT), Handler)
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
