#!/usr/bin/env bash
# Drive the full stress_tests bench against locally-hosted Ollama GGUFs.
#
# Loops over (repo, quant) combos pulled by tools/ollama_pull_targets.sh,
# runs the standard run_suite.sh against the Ollama OpenAI-compatible
# endpoint, and stashes per-combo SUMMARY.md under docs/benchmarks/local/.
#
# Usage:
#   bash bench/scripts/run_local_suite.sh                    # full sweep
#   COMBOS="...:Q4_K_M ...:Q8_0" bash .../run_local_suite.sh # subset
#   MAX_TURNS=20 bash .../run_local_suite.sh                 # raise turn cap
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUT_DIR="$REPO_ROOT/docs/benchmarks/local"
mkdir -p "$OUT_DIR"

# Default combo set — Gemma-4 fable5 variants at Q4_K_M and Q8_0.
# Qwythos-9B is intentionally excluded: its `qwen35` architecture is not
# supported by the llama.cpp shipped with ollama 0.20.2 (load fails with
# "unknown model architecture: 'qwen35'"). Re-add when ollama updates, or
# run it via a recent llama-server build directly.
DEFAULT_COMBOS=(
  "hf.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF:Q4_K_M"
  "hf.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF:Q8_0"
  "hf.co/yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF:Q4_K_M"
  "hf.co/yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF:Q8_0"
)
if [ -n "${COMBOS:-}" ]; then
  read -ra COMBOS_ARR <<< "$COMBOS"
else
  COMBOS_ARR=("${DEFAULT_COMBOS[@]}")
fi

OVERVIEW="$OUT_DIR/OVERVIEW.md"
{
  echo "# Local GGUF bench overview"
  echo
  echo "started: $(date -Iseconds)"
  echo "endpoint: http://127.0.0.1:11434/v1/chat/completions"
  echo
  echo "| combo | pass | fail | no-score | summary |"
  echo "|---|---:|---:|---:|---|"
} > "$OVERVIEW"

ok_all=0
total=${#COMBOS_ARR[@]}
i=0

for combo in "${COMBOS_ARR[@]}"; do
  i=$((i+1))
  echo "=================================================="
  echo "[$i/$total] $combo"
  echo "=================================================="

  # Sanity: model loaded?
  if ! ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -Fxq "$combo"; then
    echo "  SKIP (not in ollama list — pull first)"
    safe=$(echo "$combo" | tr '/:' '__')
    echo "| \`$combo\` | - | - | - | not pulled |" >> "$OVERVIEW"
    continue
  fi

  # Smoke test first. Skip the full suite if tool-calling is broken even
  # after the normalizer — that's the same 1/6 trap as v0.2 gemma-12B-coder.
  echo "--- tool_call smoke ---"
  if ! SMOKE_SCRIPT_DIR="$SCRIPT_DIR" \
       ENDPOINT="http://127.0.0.1:11434/v1/chat/completions" \
       API_KEY="ollama" \
       bash "$SCRIPT_DIR/tool_call_smoke.sh" "$combo" 2>&1 | tee /tmp/smoke_last.log; then
    echo "  SMOKE FAIL — recording and moving on"
    echo "| \`$combo\` | - | - | - | smoke fail (see overview log) |" >> "$OVERVIEW"
    continue
  fi

  # Full suite via standard runner, no NIM env source, local endpoint.
  echo "--- full suite ---"
  MODEL="$combo" \
  MAX_TURNS="${MAX_TURNS:-15}" \
  NIM_URL="http://127.0.0.1:11434/v1/chat/completions" \
  NIM_TIMEOUT="${NIM_TIMEOUT:-600}" \
  NIM_NO_SOURCE_ENV=1 \
  NVIDIA_API_KEY="" \
    bash "$SCRIPT_DIR/run_suite.sh"
  rc=$?

  # Locate the SUMMARY the runner just wrote.
  sum=$(ls -td /tmp/nim_suite_*/SUMMARY.md 2>/dev/null | head -1)
  if [ -z "$sum" ] || [ ! -f "$sum" ]; then
    echo "| \`$combo\` | - | - | - | runner exit=$rc, no SUMMARY |" >> "$OVERVIEW"
    continue
  fi

  pass=$(awk -F'|' '/^\| [^|]+ \| PASS /     {n++} END {print n+0}' "$sum")
  fail=$(awk -F'|' '/^\| [^|]+ \| FAIL /     {n++} END {print n+0}' "$sum")
  no=$(awk   -F'|' '/^\| [^|]+ \| NO-SCORE / {n++} END {print n+0}' "$sum")

  safe=$(echo "$combo" | tr '/:' '__')
  cp "$sum" "$OUT_DIR/${safe}.md"
  echo "| \`$combo\` | $pass | $fail | $no | [${safe}.md](./${safe}.md) |" >> "$OVERVIEW"
  if [ "$pass" -ge 4 ]; then
    ok_all=$((ok_all+1))
  fi
done

echo
echo "=================================================="
echo "overview: $OVERVIEW"
echo "=================================================="
cat "$OVERVIEW"
echo
echo "combos with pass>=4: $ok_all / $total"
