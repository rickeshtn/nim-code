#!/usr/bin/env bash
# Returns 0 if implementation passes; 1 otherwise. Prints PASS/FAIL line.
set +e
python3 -m pytest test_lru.py -q --tb=no 2>&1 >/tmp/nim_score.log
rc=$?
if [ $rc -eq 0 ]; then
  echo "PASS: 01_lru_cache"
else
  echo "FAIL: 01_lru_cache"
  tail -n 20 /tmp/nim_score.log
fi
exit $rc
