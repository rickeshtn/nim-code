#!/usr/bin/env bash
set +e
python3 -m pytest test_toposort.py -q --tb=no 2>&1 >/tmp/nim_score.log
rc=$?
[ $rc -eq 0 ] && echo "PASS: 02_toposort" || { echo "FAIL: 02_toposort"; tail -n 20 /tmp/nim_score.log; }
exit $rc
