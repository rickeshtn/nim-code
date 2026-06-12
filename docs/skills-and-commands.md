# Skills and Slash Commands in nimcode

nimcode extends the opencode TUI with **slash commands** (one-shot reusable prompts) and **skills** (model-invokable expert prompts with metadata). Both work out of the box — nimcode ships a built-in set, and you can add your own.

This guide covers what they are, how they're loaded, how to add your own, and how to import an existing Claude Code skill/command library.

---

## TL;DR

- **Slash commands** — type `/<name>` inside the TUI to expand a saved prompt template. Files live in `~/.config/opencode/commands/<name>.md`.
- **Skills** — markdown prompts with YAML frontmatter that the model invokes when relevant. Files live in `~/.config/opencode/skill/<name>/SKILL.md`.
- nimcode bundles a starter set (`/compact-graph`, `/load-graph`) — installed automatically.
- Run `nimcode sync-claude` once if you already have `~/.claude/skills` and `~/.claude/commands` and want them in nimcode too.

---

## What's the difference?

| | **Slash command** | **Skill** |
|---|---|---|
| How you invoke it | Type `/name` in the TUI | Model decides based on context |
| Where prompt lives | A single markdown file | A folder with `SKILL.md` + optional resources |
| Frontmatter | Optional | Required (`name`, `description`, `allowed-tools`) |
| Discoverability | User-driven, explicit | Automatic, based on the description match |
| Typical use | "Do this exact thing now" | "When the user asks about X, follow this playbook" |

Use a slash command when YOU want to trigger a specific prompt. Use a skill when you want the model to follow a specific playbook whenever a class of question comes up.

---

## Slash Commands

### Built-in commands

nimcode ships with:

| Command | What it does |
|---------|---|
| `/load-graph` | Reads `.agent-memory/graph/latest.md` and rehydrates working context (active goals, architecture, decisions, blockers, next actions). Run at the start of a session. |

Run `nimcode` and type `/load-graph` to see it in action.

### Writing your own command

A slash command is a single markdown file. The body becomes the prompt; `$ARGUMENTS` is replaced by whatever the user types after the slash command name.

```bash
# Create the command file
cat > ~/.config/opencode/commands/explain.md <<'EOF'
Explain what the code in $ARGUMENTS does. Cover:
1. What problem it solves
2. The data flow
3. Edge cases handled
4. Anything that looks wrong
EOF
```

Now in the TUI:

```
/explain src/auth/jwt.py
```

opencode loads the file, substitutes `$ARGUMENTS` with `src/auth/jwt.py`, and sends it as the prompt.

### Command file format

```markdown
# Title (ignored by the model — just for readability)

The actual prompt sent to the model goes here.
Use $ARGUMENTS where the user's input should be inserted.

You can write multiple paragraphs, code blocks, or numbered steps.
```

No frontmatter required. Just markdown.

### Where commands are loaded from

| Path | Scope |
|------|-------|
| `~/.config/opencode/commands/*.md` | Global — available in every project |
| `<project>/.opencode/commands/*.md` | Per-project — only that project |

Per-project commands override global ones with the same name.

### Renaming, deleting, organizing

- **Rename:** just rename the file — `mv ~/.config/opencode/commands/old.md ~/.config/opencode/commands/new.md`
- **Delete:** `rm ~/.config/opencode/commands/<name>.md`
- **List:** `ls ~/.config/opencode/commands/`

The TUI rescans on next launch.

---

## Skills

### Built-in skills

nimcode ships with:

| Skill | What it does |
|-------|---|
| `compact-graph` | Compresses the current session into a dense knowledge graph at `.agent-memory/graph/`. Pair with `/load-graph` next session to preserve context across model restarts. |

Skills aren't invoked by typing — the model uses them when the description matches what the user is asking.

### Writing your own skill

A skill is a folder containing a `SKILL.md` file with YAML frontmatter.

```bash
mkdir -p ~/.config/opencode/skill/security-review
cat > ~/.config/opencode/skill/security-review/SKILL.md <<'EOF'
---
name: security-review
description: Audit code for OWASP Top 10 vulnerabilities — SQL injection, XSS, auth bypass, secrets leakage, SSRF. Use when the user asks for a security review, audit, or vulnerability assessment.
allowed-tools: Read, Grep, Glob, Bash
---

# Security Review

When the user asks for a security review:

1. Identify all user-input boundaries (HTTP handlers, CLI args, file reads)
2. Trace each input through the code
3. Flag any path that hits a sink (SQL exec, shell exec, template render) without sanitization
4. Check secret handling — look for hardcoded keys, weak crypto, plaintext storage
5. Output: a numbered list of findings with severity (CRITICAL/HIGH/MEDIUM), file:line, and suggested fix

Be specific. Don't list theoretical risks — only what you can prove from the code in front of you.
EOF
```

The model now invokes this skill whenever the user asks for a security review, audit, or vulnerability check — based on matching `description`.

### Skill file format

```yaml
---
name: skill-name              # required, must match folder name
description: One-line summary the model uses to decide if this skill applies. Be specific about what triggers it.
allowed-tools: Read, Write, Edit, Bash    # comma-separated list of tools this skill is allowed to use
---

# Skill Name (free-form markdown body)

The instructions the model follows when this skill is invoked.
Be procedural — numbered steps, decision points, output format.
```

The `description` field is what the model matches against. Make it specific. **"Use when the user asks for X, Y, or Z"** is better than **"Helps with security stuff."**

### Where skills are loaded from

| Path | Scope |
|------|-------|
| `~/.config/opencode/skill/<name>/SKILL.md` | Global — available in every project |
| `<project>/.opencode/skill/<name>/SKILL.md` | Per-project |
| Custom paths via `skills.paths` in `~/.config/opencode/opencode.json` | Wherever you want |

### Adding extra skill folders

Edit `~/.config/opencode/opencode.json`:

```json
{
  "skills": {
    "paths": [
      "/home/you/my-skill-library",
      "/home/you/.claude/skills"
    ]
  }
}
```

opencode loads `<path>/<name>/SKILL.md` from each entry.

---

## Importing Claude Code skills + commands

If you already use Claude Code and have a library in `~/.claude/`, nimcode can pick them up:

```bash
nimcode sync-claude
```

This:
1. Adds `~/.claude/skills` to `skills.paths` in `~/.config/opencode/opencode.json`
2. Copies each `~/.claude/commands/*.md` into `~/.config/opencode/commands/` with a `<!-- nim-code:synced-from-claude -->` marker
3. Skips files you've manually edited (no marker = user-owned, left alone)

Run it again whenever you add new Claude skills — it's idempotent.

### What if I edit a synced command?

Open the file in `~/.config/opencode/commands/<name>.md` and delete the first line (`<!-- nim-code:synced-from-claude -->`). Now it's user-owned and re-syncs won't overwrite it.

### Reverting

```bash
# Remove all sync-managed commands
grep -lrFx '<!-- nim-code:synced-from-claude -->' ~/.config/opencode/commands/ | xargs rm

# Remove the skills path from opencode.json (edit manually)
```

---

## Examples — Building a Useful Skill Library

### Example 1 — `/test` slash command

```bash
cat > ~/.config/opencode/commands/test.md <<'EOF'
Run the test suite for the file or directory in $ARGUMENTS.

Detect the test framework:
- *.py with pytest → `pytest -xvs $ARGUMENTS`
- *.ts/*.tsx with vitest → `vitest run $ARGUMENTS`
- *.go → `go test -run . $ARGUMENTS`

If tests fail, show me the first failure with full traceback. Don't fix anything yet — just report.
EOF
```

### Example 2 — `code-review` skill

```bash
mkdir -p ~/.config/opencode/skill/code-review
cat > ~/.config/opencode/skill/code-review/SKILL.md <<'EOF'
---
name: code-review
description: Review code diffs for bugs, security issues, and reuse/simplification opportunities. Use when the user asks for a code review, asks "what's wrong with this code?", or wants feedback on a PR/diff.
allowed-tools: Read, Grep, Bash
---

# Code Review

Run `git diff` (or `git diff <base>`) to get the changes.

For each changed file:
1. **Correctness bugs** — null derefs, off-by-one, race conditions, incorrect error handling
2. **Security** — injection, auth bypass, secret leakage, missing input validation
3. **Reuse** — does this duplicate existing code? Is there a stdlib/library function?
4. **Simplification** — overly clever code, unnecessary abstractions

Output: numbered findings, each with severity (CRITICAL / HIGH / MEDIUM / LOW), file:line, and a one-line fix recommendation. Don't list nits about formatting — assume a linter handles those.
EOF
```

### Example 3 — `compact-graph` + `load-graph` workflow

Already bundled. The full cycle:

1. **End of session:** type `/compact-graph` — the model writes `.agent-memory/graph/<timestamp>-compact-graph.md` and updates `latest.md`. Highly compressed: nodes, edges, decisions, facts, next actions.
2. **Start of next session:** type `/load-graph` — the model reads `latest.md` and rehydrates working memory. It prints active goals, architecture, decisions made, blockers, and next actions, then continues.

This survives context compaction and session restarts. Particularly useful when nimcode hits the NIM context cap (often lower than the model's native max).

---

## Loading order and conflicts

If the same name exists in multiple places, opencode picks the most specific:

```
project skill > project command > global skill > global command > skills.paths entries
```

To check what got loaded, run nimcode and type `/` — the autocomplete list shows all known commands.

For skills, the model only "sees" the descriptions — there's no autocomplete. To verify a skill is loaded:

```bash
ls ~/.config/opencode/skill/         # global skills
ls .opencode/skill/                  # per-project skills (in your repo)
```

---

## Versioning skills with your project

Per-project skills under `<project>/.opencode/skill/` should be committed to git. The team gets the same playbook.

```
my-project/
├── .opencode/
│   ├── skill/
│   │   ├── api-style/SKILL.md       # our API conventions
│   │   └── deploy-check/SKILL.md    # pre-deploy verification
│   └── commands/
│       └── ship.md                  # /ship — runs tests + builds + deploys
├── src/
└── ...
```

Add to your README:

> ```bash
> nimcode    # picks up .opencode/ automatically
> ```

---

## Troubleshooting

**`/my-command` doesn't autocomplete.** Check the file is at `~/.config/opencode/commands/my-command.md` (singular `command` is wrong, must be `commands`). Restart nimcode.

**The model doesn't seem to invoke my skill.** The `description` is too generic. Add "Use when the user asks about <specific trigger>" to nudge it.

**`nimcode sync-claude` reports "user-edited target exists".** That command file in `~/.config/opencode/commands/` lacks the sync marker. If you want it overwritten, delete it first, then re-run sync.

**My skill folder isn't being picked up.** opencode expects `<path>/<skill-name>/SKILL.md`. The folder name must match the `name:` field in the frontmatter. Folder name `my-skill` + `name: my_skill` won't load.

**Per-project skills aren't being applied.** Verify the path is `<project>/.opencode/skill/<name>/SKILL.md` (singular `skill`). Per-project commands use `.opencode/commands/` (plural). Yes, the singular/plural difference is opencode's convention — not ours.

---

## Reference

| Path | What it is |
|------|-----------|
| `~/.config/opencode/commands/<name>.md` | Global slash command |
| `~/.config/opencode/skill/<name>/SKILL.md` | Global skill |
| `<project>/.opencode/commands/<name>.md` | Per-project slash command |
| `<project>/.opencode/skill/<name>/SKILL.md` | Per-project skill |
| `~/.config/opencode/opencode.json` → `skills.paths` | Extra skill folders |
| `~/.config/nim-code/sync_claude.py` | The sync helper |
| Repo `skills/` and `commands/` | nimcode's bundled defaults (deployed by install.sh) |
