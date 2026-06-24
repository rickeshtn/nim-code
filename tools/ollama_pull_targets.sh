#!/usr/bin/env bash
# Idempotent puller for the local GGUF eval set.
#
# Writes models into $OLLAMA_MODELS (already configured to
# /media/rickeshtn/.../ollama-models via the ollama systemd unit).
# Skips combos already present in `ollama list`.
#
# Usage:
#   bash tools/ollama_pull_targets.sh            # pull everything missing
#   DRY_RUN=1 bash tools/ollama_pull_targets.sh  # print plan only
set -u

DRY_RUN="${DRY_RUN:-0}"

# (hf_repo, tag) pairs — one per intended quant.
TARGETS=(
  "yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF:Q2_K"
  "yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF:Q3_K_M"
  "yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF:Q4_K_M"
  "yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF:Q6_K"
  "yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF:Q8_0"

  "yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF:Q3_K_M"
  "yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF:Q4_K_M"
  "yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF:Q6_K"
  "yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF:Q8_0"

  # Qwythos base quants only — skip BF16 (won't fit 3080), MTP variants
  # (speculative-decode pairing, not for single-model bench), and mmproj
  # (vision projector — bench is text-only).
  "empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF:Q4_K_M"
  "empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF:Q5_K_M"
  "empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF:Q6_K"
  "empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF:Q8_0"
)

have() {
  ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -Fxq "$1"
}

echo "=== ollama pull plan (DRY_RUN=$DRY_RUN) ==="
total=${#TARGETS[@]}
i=0
pulled=0
skipped=0
failed=0
for t in "${TARGETS[@]}"; do
  i=$((i+1))
  tag="hf.co/${t}"
  if have "$tag"; then
    echo "[$i/$total] SKIP  $tag (already pulled)"
    skipped=$((skipped+1))
    continue
  fi
  if [ "$DRY_RUN" = "1" ]; then
    echo "[$i/$total] PLAN  $tag"
    continue
  fi
  echo "[$i/$total] PULL  $tag"
  if ollama pull "$tag"; then
    pulled=$((pulled+1))
  else
    echo "[$i/$total] FAIL  $tag (rc=$?)" >&2
    failed=$((failed+1))
  fi
done

echo
echo "=== done: pulled=$pulled skipped=$skipped failed=$failed total=$total ==="
[ "$failed" -eq 0 ]
