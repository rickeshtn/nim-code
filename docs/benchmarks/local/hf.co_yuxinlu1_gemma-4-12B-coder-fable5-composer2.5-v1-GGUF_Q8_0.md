# nim-code stress-suite results

model: `hf.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1-GGUF:Q8_0`
started: 2026-06-24T23:30:02+08:00

| task | result | turns | tool_calls | tool_errors | duration_s |
|---|---|---|---|---|---|
| 01_lru_cache | FAIL | 3 | 2 | 0 | 18.9 |
| 02_toposort | FAIL | 3 | 2 | 0 | 19.8 |
| 03_rate_limiter | FAIL | 3 | 2 | 0 | 28.0 |
| 04_btree | FAIL | 1 | 0 | 0 | 31.1 |
| 05_minigrep | FAIL | 1 | 0 | 0 | 25.5 |
| 99_refactor | FAIL | 4 | 3 | 0 | 223.2 |
