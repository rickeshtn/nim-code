# nim-code stress-suite results

model: `qwythos-9B-Q4_K_M-native`
started: 2026-06-25T06:45:40+08:00

| task | result | turns | tool_calls | tool_errors | duration_s |
|---|---|---|---|---|---|
| 01_lru_cache | FAIL | 10 | 9 | 0 | 33.4 |
| 02_toposort | PASS | 3 | 3 | 0 | 14.5 |
| 03_rate_limiter | PASS | 3 | 3 | 0 | 13.5 |
| 04_btree | FAIL | 4 | 3 | 0 | 76.2 |
| 05_minigrep | FAIL | 1 | 0 | 0 | 48.9 |
| 99_refactor | FAIL | 3 | 2 | 0 | 7.0 |
