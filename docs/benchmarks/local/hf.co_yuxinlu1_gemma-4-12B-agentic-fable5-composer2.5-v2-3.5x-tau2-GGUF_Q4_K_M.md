# nim-code stress-suite results

model: `hf.co/yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF:Q4_K_M`
started: 2026-06-24T23:36:05+08:00

| task | result | turns | tool_calls | tool_errors | duration_s |
|---|---|---|---|---|---|
| 01_lru_cache | PASS | 3 | 2 | 0 | 20.5 |
| 02_toposort | PASS | 4 | 4 | 0 | 20.7 |
| 03_rate_limiter | PASS | 8 | 7 | 0 | 50.1 |
| 04_btree | FAIL | 5 | 4 | 0 | 141.6 |
| 05_minigrep | FAIL | 6 | 5 | 0 | 448.7 |
| 99_refactor | FAIL | 4 | 3 | 1 | 73.9 |
