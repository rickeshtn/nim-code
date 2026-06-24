# nim-code stress-suite results

model: `hf.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF:Q4_K_M`
started: 2026-06-24T23:25:19+08:00

| task | result | turns | tool_calls | tool_errors | duration_s |
|---|---|---|---|---|---|
| 01_lru_cache | FAIL | 2 | 1 | 0 | 6.7 |
| 02_toposort | FAIL | 2 | 1 | 0 | 6.9 |
| 03_rate_limiter | PASS | 2 | 1 | 0 | 13.3 |
| 04_btree | FAIL | 1 | 0 | 0 | 25.7 |
| 05_minigrep | FAIL | 2 | 1 | 0 | 18.7 |
| 99_refactor | FAIL | 4 | 3 | 0 | 169.8 |
