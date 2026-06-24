# nim-code stress-suite results

model: `hf.co/yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF:Q6_K`
started: 2026-06-25T07:03:38+08:00

| task | result | turns | tool_calls | tool_errors | duration_s |
|---|---|---|---|---|---|
| 01_lru_cache | PASS | 3 | 3 | 0 | 37.2 |
| 02_toposort | PASS | 3 | 3 | 0 | 13.3 |
| 03_rate_limiter | PASS | 4 | 3 | 0 | 172.8 |
| 04_btree | FAIL | 5 | 4 | 0 | 224.8 |
| 05_minigrep | FAIL | 8 | 7 | 0 | 86.9 |
| 99_refactor | FAIL | 5 | 4 | 0 | 42.8 |
