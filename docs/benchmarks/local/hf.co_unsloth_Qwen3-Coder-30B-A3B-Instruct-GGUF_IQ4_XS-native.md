# nim-code stress-suite results

model: `hf.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:IQ4_XS`
started: 2026-06-25T08:14:21+08:00

| task | result | turns | tool_calls | tool_errors | duration_s |
|---|---|---|---|---|---|
| 01_lru_cache | FAIL | 1 | 0 | 0 | 14.3 |
| 02_toposort | PASS | 4 | 4 | 0 | 18.6 |
| 03_rate_limiter | PASS | 7 | 7 | 0 | 20.9 |
| 04_btree | FAIL | 4 | 3 | 0 | 44.3 |
| 05_minigrep | PASS | 4 | 4 | 0 | 27.9 |
| 99_refactor | FAIL | 2 | 1 | 0 | 7.4 |
