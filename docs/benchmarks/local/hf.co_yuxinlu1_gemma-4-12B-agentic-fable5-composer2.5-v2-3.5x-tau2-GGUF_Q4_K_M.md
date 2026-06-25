# nim-code stress-suite results

model: `hf.co/yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF:Q4_K_M`
started: 2026-06-25T07:40:37+08:00

| task | result | turns | tool_calls | tool_errors | duration_s |
|---|---|---|---|---|---|
| 01_lru_cache | PASS | 4 | 3 | 0 | 419.3 |
| 02_toposort | PASS | 5 | 4 | 0 | 357.5 |
| 03_rate_limiter | PASS | 3 | 2 | 0 | 53.7 |
| 04_btree | FAIL | 1 | 0 | 0 | 198.7 |
| 05_minigrep | FAIL | 15 | 15 | 0 | 612.9 |
| 99_refactor | FAIL | 6 | 5 | 1 | 328.9 |
