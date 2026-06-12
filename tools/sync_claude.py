#!/usr/bin/env python3
"""
Sync ~/.claude/skills and ~/.claude/commands into opencode so nimcode can
use them as native skills and slash commands.

Skills: opencode reads ~/.config/opencode/skill/<name>/SKILL.md. We don't
copy — we add ~/.claude/skills to opencode.json's `skills.paths` field so
opencode loads them in-place.

Commands: opencode reads ~/.config/opencode/commands/<name>.md. We copy
each ~/.claude/commands/*.md to that directory, prefixing nim-code-managed
files with a header marker so future re-syncs can clean up safely.

Run via: python3 tools/sync_claude.py
Or via:  nimcode sync-claude
"""
from __future__ import annotations
import json
import os
import shutil
import sys
from pathlib import Path

HOME = Path.home()
CLAUDE_SKILLS = HOME / ".claude" / "skills"
CLAUDE_COMMANDS = HOME / ".claude" / "commands"
OPENCODE_CFG = HOME / ".config" / "opencode" / "opencode.json"
OPENCODE_COMMANDS = HOME / ".config" / "opencode" / "commands"
MARKER = "<!-- nim-code:synced-from-claude -->"


def sync_skills() -> int:
    if not CLAUDE_SKILLS.is_dir():
        print(f"skip skills: {CLAUDE_SKILLS} not found")
        return 0
    if not OPENCODE_CFG.is_file():
        print(f"error: {OPENCODE_CFG} not found — run install.sh first", file=sys.stderr)
        return 1
    cfg = json.loads(OPENCODE_CFG.read_text())
    skills = cfg.setdefault("skills", {})
    paths = skills.setdefault("paths", [])
    target = str(CLAUDE_SKILLS)
    if target not in paths:
        paths.append(target)
        OPENCODE_CFG.write_text(json.dumps(cfg, indent=2) + "\n")
        print(f"+ skills.paths: {target}")
    else:
        print(f"= skills.paths already contains {target}")
    n = sum(1 for p in CLAUDE_SKILLS.iterdir() if (p / "SKILL.md").is_file())
    print(f"  -> {n} skill(s) available")
    return 0


def sync_commands() -> int:
    if not CLAUDE_COMMANDS.is_dir():
        print(f"skip commands: {CLAUDE_COMMANDS} not found")
        return 0
    OPENCODE_COMMANDS.mkdir(parents=True, exist_ok=True)

    for stale in OPENCODE_COMMANDS.glob("*.md"):
        try:
            head = stale.read_text(errors="ignore").splitlines()[:1]
            if head and MARKER in head[0]:
                stale.unlink()
        except OSError:
            pass

    added = skipped = 0
    for src in sorted(CLAUDE_COMMANDS.glob("*.md")):
        dst = OPENCODE_COMMANDS / src.name
        if dst.exists():
            head = dst.read_text(errors="ignore").splitlines()[:1]
            if not (head and MARKER in head[0]):
                print(f"  skip {src.name}: user-edited target exists")
                skipped += 1
                continue
        body = src.read_text()
        dst.write_text(f"{MARKER}\n{body}")
        added += 1
    print(f"commands: synced {added}, skipped {skipped} -> {OPENCODE_COMMANDS}")
    return 0


def main() -> int:
    if not shutil.which("opencode"):
        print("warning: opencode CLI not on PATH — install nim-code first", file=sys.stderr)
    rc = sync_skills()
    rc |= sync_commands()
    return rc


if __name__ == "__main__":
    sys.exit(main())
