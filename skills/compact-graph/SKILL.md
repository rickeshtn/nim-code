---
name: compact-graph
description: Compress the current session into a dense machine-readable knowledge graph with minimal English.
allowed-tools: Read, Write, Edit, Bash
---

# /compact-graph

When user runs `/compact-graph`, extract all useful session/project knowledge and store it as a compact graph.

Goal:
- Preserve maximum reusable information.
- Use minimum English.
- Prefer symbols, ids, edges, tags, paths, commands, decisions.
- Drop filler words.
- Drop vowels in common labels when readable.
- No paragraphs unless absolutely needed.

Output path:

.agent-memory/graph/YYYYMMDD-HHMM-compact-graph.md

Also update:

.agent-memory/graph/latest.md

## Graph format

Use this structure:

```md
# CGRAPH v1
ts: <ISO_TIME>
proj: <project_name>
root: <repo_path>
sess: <session_id_if_known>

## NODES
N:<id>|t:<type>|nm:<name>|tags:<tag1,tag2>|st:<state>|src:<file/path/msg>

## EDGES
E:<src>-><dst>|r:<relation>|w:<weight>|ctx:<short_context>

## FACTS
F:<id>|<compressed_fact>

## DECS
D:<id>|q:<decision_question>|ch:<chosen>|why:<compressed_reason>|alts:<alt1,alt2>

## TASKS
T:<id>|st:<todo/doing/done/block>|pri:<H/M/L>|own:<agent/user>|txt:<compressed_task>

## FILES
P:<path>|role:<role>|chg:<yes/no>|note:<compressed_note>

## CMDS
C:<id>|cmd:<command>|why:<reason>|out:<important_output>

## OPENQ
Q:<id>|q:<question>|need:<needed_info>

## NEXT
NX:<step_number>|<next_action>
