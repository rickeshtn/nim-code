#!/usr/bin/env bash
set +e
python3 -m pytest test_refactor.py -q --tb=short 2>&1 >/tmp/nim_score.log
rc=$?
# bonus: penalize if godclass.py wasn't deleted
if [ -f godclass.py ]; then
  echo "WARN: godclass.py still present (refactor incomplete)"
fi
[ $rc -eq 0 ] && echo "PASS: 99_refactor" || { echo "FAIL: 99_refactor"; tail -n 40 /tmp/nim_score.log; }
exit $rc
