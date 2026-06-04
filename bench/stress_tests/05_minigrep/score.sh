#!/usr/bin/env bash
set +e
python3 -m pytest test_mg.py -q --tb=no 2>&1 >/tmp/nim_score.log
rc=$?
[ $rc -eq 0 ] && echo "PASS: 05_minigrep" || { echo "FAIL: 05_minigrep"; tail -n 40 /tmp/nim_score.log; }
exit $rc
