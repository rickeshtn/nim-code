#!/usr/bin/env python3
"""Minimal headless agent loop against NIM. Same tool-calling contract opencode
uses, just no TUI — so it can be driven from a non-interactive shell.

Tools exposed to the model:
  - write_file(path, content)        write a file (creates dirs)
  - read_file(path)                  read a file
  - run_bash(cmd, timeout_s=60)      run a shell command, return rc+stdout+stderr
  - finish(summary)                  terminate the loop

Usage:
  NVIDIA_API_KEY=... python3 headless_agent.py \
    --workdir /tmp/run_01 \
    --prompt-file /tmp/run_01/PROMPT.md \
    --model meta/llama-3.3-70b-instruct \
    --max-turns 12
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request
import urllib.error

try:
    from tool_call_normalizer import normalize_response as _normalize_tool_calls
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from tool_call_normalizer import normalize_response as _normalize_tool_calls

NIM_URL = os.environ.get("NIM_URL", "https://integrate.api.nvidia.com/v1/chat/completions")
_LOCAL_ENDPOINT = any(h in NIM_URL for h in ("127.0.0.1", "localhost", "0.0.0.0"))
# Local-endpoint tools handling:
#   "embed"   — splice tool schemas into the system message; drop the OpenAI
#               tools field. Required for Ollama, which rejects the tools
#               field for community GGUFs without tool-aware Modelfiles.
#   "native"  — send the OpenAI tools field unchanged. Required for
#               llama-server with --jinja (Qwen3.5/Qwythos chat templates
#               render tools into the format the model was trained on,
#               yielding a clean tool_calls[] response). Also fine for any
#               OpenAI-compat endpoint that supports tools natively.
_LOCAL_TOOLS_MODE = os.environ.get("BENCH_LOCAL_TOOLS_MODE", "embed").lower()

TOOLS = [
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Write content to a file (overwrites). Creates parent dirs as needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to workdir."},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    }},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a file's full contents.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    }},
    {"type": "function", "function": {
        "name": "run_bash",
        "description": "Run a bash command in the workdir. Returns rc, stdout, stderr (each truncated to 4 KB).",
        "parameters": {
            "type": "object",
            "properties": {
                "cmd": {"type": "string"},
                "timeout_s": {"type": "integer", "default": 60},
            },
            "required": ["cmd"],
        },
    }},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Call ONLY after ./score.sh prints PASS. Terminates the agent loop.",
        "parameters": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    }},
]

SYSTEM = """You are a coding agent. You have four tools: write_file, read_file, run_bash, finish.
Workflow:
  1. Implement the task by writing files.
  2. Run ./score.sh via run_bash.
  3. If FAIL, read the error, fix, repeat.
  4. ONLY call finish() after score.sh prints PASS.
Be terse. Do not narrate plans. Just call tools."""


def truncate(s, limit=4096):
    if s is None:
        return ""
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n... [truncated {len(s)-limit} chars]"


def tool_write_file(workdir, path, content):
    p = (workdir / path).resolve()
    if workdir.resolve() not in p.parents and p != workdir.resolve():
        return {"error": f"refused: path {p} outside workdir"}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return {"ok": True, "bytes": len(content), "path": str(p.relative_to(workdir))}


def tool_read_file(workdir, path):
    p = (workdir / path).resolve()
    if not p.exists():
        return {"error": f"not found: {path}"}
    try:
        return {"content": truncate(p.read_text(), 16000)}
    except Exception as e:
        return {"error": str(e)}


def tool_run_bash(workdir, cmd, timeout_s=60):
    try:
        r = subprocess.run(
            ["bash", "-lc", cmd],
            cwd=workdir, capture_output=True, text=True,
            timeout=max(1, min(int(timeout_s), 180)),
        )
        return {
            "rc": r.returncode,
            "stdout": truncate(r.stdout),
            "stderr": truncate(r.stderr),
        }
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}


def _local_messages_with_embedded_tools(messages):
    """Local Ollama rejects requests with `tools` for models whose Modelfile
    doesn't declare tool support — which is the case for every community
    fine-tune pulled directly from `hf.co/...`. Workaround: splice the tool
    schemas into the system message and rely on the normalizer to parse the
    wrapped tool calls (`<tool_call>fn(...)</tool_call>`, JSON, etc.) out
    of message.content. Tool results (`role: tool`) are repackaged as user
    messages because community fine-tunes rarely see the `tool` role.
    """
    fn_specs = [t["function"] for t in TOOLS]
    tools_block = (
        "\n\n# Available tools\n"
        "Call EXACTLY ONE tool per response by emitting it in your message body. "
        "Accepted forms (use any one; pick what matches your training):\n"
        "  <tool_call>fn_name(arg1=val1, arg2=\"...\")</tool_call>\n"
        "  <tool_call>{\"name\":\"fn_name\",\"arguments\":{...}}</tool_call>\n"
        "  ```json\n  {\"name\":\"fn_name\",\"arguments\":{...}}\n  ```\n"
        "After emitting one tool call, stop generating. Do not narrate.\n\n"
        "Tools:\n" + json.dumps(fn_specs, indent=2)
    )
    out = []
    sys_done = False
    for m in messages:
        if m["role"] == "system" and not sys_done:
            out.append({"role": "system", "content": (m.get("content") or "") + tools_block})
            sys_done = True
        elif m["role"] == "tool":
            # Repackage tool-result as user content so models without the
            # `tool` role still see the previous call's result.
            out.append({
                "role": "user",
                "content": f"[tool_result id={m.get('tool_call_id','')}]\n{m.get('content','')}",
            })
        elif m["role"] == "assistant":
            # Strip tool_calls field — keep the content (which may already
            # be the wrapped form the model emitted) so the model sees its
            # own history coherently.
            out.append({"role": "assistant", "content": m.get("content") or ""})
        else:
            out.append(m)
    if not sys_done:
        out.insert(0, {"role": "system", "content": "You are a coding agent." + tools_block})
    return out


def call_nim(api_key, model, messages, retries=3):
    _max_tok = int(os.environ.get("BENCH_MAX_TOKENS", "8192"))
    if _LOCAL_ENDPOINT and _LOCAL_TOOLS_MODE == "embed":
        body = json.dumps({
            "model": model,
            "messages": _local_messages_with_embedded_tools(messages),
            "max_tokens": _max_tok,
            "temperature": 0.2,
        }).encode()
    else:
        body = json.dumps({
            "model": model,
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto",
            "max_tokens": _max_tok,
            "temperature": 0.2,
        }).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(NIM_URL, data=body, headers=headers)
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=int(os.environ.get("NIM_TIMEOUT", "120"))) as resp:
                raw = resp.read()
                raw = _normalize_tool_calls(raw)
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.read()[:200]!r}"
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(last_err)
        except Exception as e:
            last_err = repr(e); time.sleep(2 ** attempt)
    raise RuntimeError(f"NIM call failed after {retries} retries: {last_err}")


def _approx_tokens(messages):
    """~4 chars/token, +50 overhead per message for role/tool_calls boilerplate."""
    n = 0
    for m in messages:
        n += len(str(m.get("content", ""))) // 4 + 50
        for tc in (m.get("tool_calls") or []):
            n += len(str(tc)) // 4
    return n


def _summarize_chunk(chunk_messages, model, api_key):
    """One model call to compress a slice of the transcript into a short
    abstract. Independent of the bench tools — just plain chat."""
    transcript = []
    for m in chunk_messages:
        role = m.get("role", "?")
        body = m.get("content", "")[:1500]
        if m.get("tool_calls"):
            body = (body + "\n" if body else "") + "tool_calls=" + str(m["tool_calls"])[:800]
        transcript.append(f"[{role}] {body}")
    summary_messages = [
        {"role": "system",
         "content": ("You are summarising an agent transcript so the agent can continue "
                     "the task with a smaller context window. Preserve: files written and "
                     "their paths, exact function signatures created, current bug/error, "
                     "test results, the immediate next step. Drop chit-chat. Output 200 words max.")},
        {"role": "user", "content": "\n\n".join(transcript)},
    ]
    body = json.dumps({"model": model, "messages": summary_messages,
                       "max_tokens": 800, "temperature": 0.0}).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(NIM_URL, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=int(os.environ.get("NIM_TIMEOUT", "120"))) as resp:
            r = json.loads(resp.read())
        return r["choices"][0]["message"].get("content") or "[summary unavailable]"
    except Exception as e:
        return f"[summary failed: {e!r}]"


def _compact_recursive(messages, model, api_key, budget, depth=0):
    """Recursive context compaction. If the middle slice is itself larger
    than half the budget, recurse on it before summarising — that's the
    'recursion over context' lever.

    Keeps the system prompt and the most recent 2 messages intact, replaces
    the middle with a summary. Returns the new message list.
    """
    if _approx_tokens(messages) <= budget or len(messages) <= 4 or depth > 4:
        return messages
    head = messages[:1]            # system prompt — never drop
    tail = messages[-2:]           # latest user + assistant — never drop
    middle = messages[1:-2]
    if not middle:
        return messages
    # If middle alone exceeds half the budget, recurse on it first.
    if _approx_tokens(middle) > budget // 2 and len(middle) > 4:
        middle = _compact_recursive(middle, model, api_key, budget // 2, depth + 1)
    summary = _summarize_chunk(middle, model, api_key)
    print(f"[ctx-recursion d={depth}] compacted {len(middle)} msgs "
          f"({_approx_tokens(middle)} -> {len(summary)//4} approx tokens)", flush=True)
    return head + [{
        "role": "user",
        "content": f"[Earlier turns summarised; see below for the active state]\n\n{summary}",
    }] + tail


def run(workdir, prompt, model, api_key, max_turns):
    workdir = pathlib.Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    ctx_budget = int(os.environ.get("BENCH_CONTEXT_BUDGET", "0"))  # 0 = disabled
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
    ]
    stats = {"turns": 0, "tool_calls": 0, "tool_errors": 0, "finished": False,
             "ctx_compactions": 0}
    for turn in range(1, max_turns + 1):
        stats["turns"] = turn
        # Recursive context compaction before each call when over budget.
        if ctx_budget > 0 and _approx_tokens(messages) > ctx_budget:
            print(f"[ctx-recursion] turn {turn}: {_approx_tokens(messages)} tokens > budget {ctx_budget}, compacting", flush=True)
            messages = _compact_recursive(messages, model, api_key, ctx_budget)
            stats["ctx_compactions"] += 1
        print(f"\n=== turn {turn} ===", flush=True)
        resp = call_nim(api_key, model, messages)
        msg = resp["choices"][0]["message"]
        # normalize: openai sdk shape
        messages.append({
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": msg.get("tool_calls") or [],
        })
        tool_calls = msg.get("tool_calls") or []
        if msg.get("content"):
            print(f"[asst] {msg['content'][:300]}", flush=True)
        if not tool_calls:
            print("[!] model emitted no tool_calls — ending loop", flush=True)
            break
        for tc in tool_calls:
            stats["tool_calls"] += 1
            fn_raw = tc["function"]["name"]
            # Community fine-tunes routinely emit CamelCase or PascalCase
            # variants of the tool names (WriteFile/RunBash/...). Canonicalize
            # so a misspelled call still dispatches rather than burning a turn.
            _TOOL_ALIASES = {
                "writefile": "write_file", "write": "write_file",
                "readfile":  "read_file",  "read":  "read_file", "cat": "read_file",
                "runbash":   "run_bash",   "run":   "run_bash",  "bash": "run_bash", "shell": "run_bash", "exec": "run_bash",
                "finish":    "finish",     "done":  "finish",
            }
            fn = _TOOL_ALIASES.get(fn_raw.lower().replace("-", "").replace("_", ""), fn_raw)
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError as e:
                stats["tool_errors"] += 1
                result = {"error": f"bad json args: {e}"}
                print(f"[tool {fn}] BAD JSON ARGS", flush=True)
            else:
                print(f"[tool {fn}] {json.dumps(args)[:200]}", flush=True)
                # Accept common aliases — models vary in arg-name fidelity.
                def _arg(*names, default=None):
                    for n in names:
                        if n in args: return args[n]
                    return default
                if fn == "write_file":
                    path = _arg("path", "file", "filename")
                    content = _arg("content", "text", "body", default="")
                    if not path:
                        result = {"error": f"missing path. got args: {list(args)}"}
                        stats["tool_errors"] += 1
                    else:
                        result = tool_write_file(workdir, path, content)
                elif fn == "read_file":
                    path = _arg("path", "file", "filename")
                    if not path:
                        result = {"error": f"missing path. got args: {list(args)}"}
                        stats["tool_errors"] += 1
                    else:
                        result = tool_read_file(workdir, path)
                elif fn == "run_bash":
                    cmd = _arg("cmd", "command", "script")
                    if not cmd:
                        result = {"error": f"missing cmd. got args: {list(args)}"}
                        stats["tool_errors"] += 1
                    else:
                        result = tool_run_bash(workdir, cmd, _arg("timeout_s", "timeout", default=60))
                    print(f"   rc={result.get('rc')} stdout_head={truncate(result.get('stdout',''),200)!r}", flush=True)
                elif fn == "finish":
                    stats["finished"] = True
                    result = {"ok": True}
                    print(f"[finish] {args.get('summary','')[:200]}", flush=True)
                else:
                    result = {"error": f"unknown tool: {fn}"}
                    stats["tool_errors"] += 1
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result)[:8000],
            })
            if fn == "finish":
                return stats
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--model", default="meta/llama-3.3-70b-instruct")
    ap.add_argument("--max-turns", type=int, default=12)
    args = ap.parse_args()

    api_key = os.environ.get("NVIDIA_API_KEY") or ""
    if not api_key and not _LOCAL_ENDPOINT:
        sys.exit("NVIDIA_API_KEY not set")

    prompt = pathlib.Path(args.prompt_file).read_text()

    t0 = time.time()
    stats = run(args.workdir, prompt, args.model, api_key, args.max_turns)
    dur = time.time() - t0

    print("\n=== agent done ===")
    print(json.dumps(stats | {"duration_s": round(dur, 1), "model": args.model}, indent=2))

    score = pathlib.Path(args.workdir) / "score.sh"
    if score.exists():
        print("\n=== final score ===")
        r = subprocess.run(["bash", str(score)], cwd=args.workdir, capture_output=True, text=True)
        print(r.stdout)
        if r.stderr.strip(): print("stderr:", r.stderr[:500])
        sys.exit(r.returncode)


if __name__ == "__main__":
    main()
