#!/usr/bin/env bash
# Run the stress_tests suite headlessly against one model.
# Usage:  MODEL=meta/llama-3.3-70b-instruct ./scripts/run_suite.sh
set -u
# Source the NIM key env only when not explicitly opted out (local-model runs
# set NIM_NO_SOURCE_ENV=1 because they hit a no-auth localhost endpoint).
if [ -z "${NIM_NO_SOURCE_ENV:-}" ] && [ -r ~/.config/nim-code/env ]; then
  . ~/.config/nim-code/env
fi

MODEL="${MODEL:-meta/llama-3.3-70b-instruct}"
MAX_TURNS="${MAX_TURNS:-15}"
TASKS=(01_lru_cache 02_toposort 03_rate_limiter 04_btree 05_minigrep 99_refactor)

# Portable script-dir resolver (BSD readlink on macOS lacks -f).
# Assumes the script is invoked by path, not via a hop through symlinks
# multiple deep. Good enough for our use.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SUITE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/stress_tests"
RUN_ROOT="/tmp/nim_suite_$(date +%s)"
mkdir -p "$RUN_ROOT"
SUMMARY="$RUN_ROOT/SUMMARY.md"

printf "# nim-code stress-suite results\n\n" > "$SUMMARY"
printf "model: \`%s\`\nstarted: %s\n\n" "$MODEL" "$(date -Iseconds)" >> "$SUMMARY"
printf "| task | result | turns | tool_calls | tool_errors | duration_s |\n" >> "$SUMMARY"
printf "|---|---|---|---|---|---|\n" >> "$SUMMARY"

for t in "${TASKS[@]}"; do
  wd="$RUN_ROOT/$t"
  cp -r "$SUITE_DIR/$t" "$wd"
  rm -rf "$wd/__pycache__"
  echo "=========================================="
  echo "=== $t"
  echo "=========================================="
  log="$wd/agent.log"
  python3 "$(dirname "$0")/headless_agent.py" \
    --workdir "$wd" \
    --prompt-file "$wd/PROMPT.md" \
    --model "$MODEL" \
    --max-turns "$MAX_TURNS" 2>&1 | tee "$log"
  agent_rc=${PIPESTATUS[0]}
  # extract stats blob from the last JSON object in the log
  stats=$(python3 - "$log" <<'PY'
import json, re, sys, pathlib
text = pathlib.Path(sys.argv[1]).read_text()
# find the last balanced {...} block that has "turns" in it
hits = []
for m in re.finditer(r'\{[^{}]*"turns"[^{}]*\}', text, re.S):
    hits.append(m.group(0))
if not hits:
    print(json.dumps({})); sys.exit()
try:
    print(json.dumps(json.loads(hits[-1])))
except Exception:
    print(json.dumps({}))
PY
)
  result=$(grep -E "^(PASS|FAIL):" "$log" | tail -1 | cut -d: -f1)
  result="${result:-NO-SCORE}"
  turns=$(echo "$stats" | python3 -c "import sys,json; d=json.loads(sys.stdin.read() or '{}'); print(d.get('turns','?'))")
  calls=$(echo "$stats" | python3 -c "import sys,json; d=json.loads(sys.stdin.read() or '{}'); print(d.get('tool_calls','?'))")
  errs=$(echo "$stats"  | python3 -c "import sys,json; d=json.loads(sys.stdin.read() or '{}'); print(d.get('tool_errors','?'))")
  dur=$(echo "$stats"   | python3 -c "import sys,json; d=json.loads(sys.stdin.read() or '{}'); print(d.get('duration_s','?'))")
  printf "| %s | %s | %s | %s | %s | %s |\n" "$t" "$result" "$turns" "$calls" "$errs" "$dur" >> "$SUMMARY"
done

echo
echo "=========================================="
echo "summary: $SUMMARY"
echo "=========================================="
cat "$SUMMARY"
