#!/usr/bin/env bash
set +e
python3 -m pytest test_btree.py -q --tb=no 2>&1 >/tmp/nim_score.log
rc=$?
[ $rc -eq 0 ] && echo "PASS: 04_btree" || { echo "FAIL: 04_btree"; tail -n 40 /tmp/nim_score.log; }
exit $rc
