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

NIM_URL = os.environ.get("NIM_URL", "https://integrate.api.nvidia.com/v1/chat/completions")

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


def call_nim(api_key, model, messages, retries=3):
    body = json.dumps({
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "max_tokens": 4096,
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(
        NIM_URL, data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=int(os.environ.get("NIM_TIMEOUT", "120"))) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.read()[:200]!r}"
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(last_err)
        except Exception as e:
            last_err = repr(e); time.sleep(2 ** attempt)
    raise RuntimeError(f"NIM call failed after {retries} retries: {last_err}")


def run(workdir, prompt, model, api_key, max_turns):
    workdir = pathlib.Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
    ]
    stats = {"turns": 0, "tool_calls": 0, "tool_errors": 0, "finished": False}
    for turn in range(1, max_turns + 1):
        stats["turns"] = turn
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
            fn = tc["function"]["name"]
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

    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
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
