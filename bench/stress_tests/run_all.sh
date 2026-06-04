#!/usr/bin/env bash
# Score every task in this dir AFTER the agent has done its work in /tmp/run_XX copies.
# Usage:  ./run_all.sh /tmp/run_01 /tmp/run_02 ...
# Or:     ./run_all.sh   (defaults to scoring in-place — only works if you ran the agent here)
set +e
HERE="$(cd "$(dirname "$0")" && pwd)"
dirs=("$@")
if [ ${#dirs[@]} -eq 0 ]; then
  dirs=("$HERE"/0*_* "$HERE"/9*_*)
fi
pass=0; fail=0
for d in "${dirs[@]}"; do
  [ -d "$d" ] || continue
  [ -x "$d/score.sh" ] || continue
  echo "=== $(basename "$d") ==="
  ( cd "$d" && ./score.sh ) && pass=$((pass+1)) || fail=$((fail+1))
done
echo
echo "summary: $pass passed, $fail failed"
[ $fail -eq 0 ]
