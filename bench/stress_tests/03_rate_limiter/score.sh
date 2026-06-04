#!/usr/bin/env bash
set +e
python3 -m pytest test_rl.py -q --tb=no 2>&1 >/tmp/nim_score.log
rc=$?
[ $rc -eq 0 ] && echo "PASS: 03_rate_limiter" || { echo "FAIL: 03_rate_limiter"; tail -n 30 /tmp/nim_score.log; }
exit $rc
