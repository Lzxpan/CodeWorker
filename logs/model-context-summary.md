# Model Context Bench

Internal benchmark summary for CodeWorker.

- Source script: `scripts/measure_context_limits.py`
- Raw data: `logs/model-context-bench.json`
- Purpose: record the practical context ceiling and completion stability of local models on this machine
- Scope: internal evaluation only; not part of the public README or end-user documentation

## qwen
- 穩定可用 context：`16384`
- 4096: ok
- 8192: ok
- 12288: ok
- 16384: ok

## gemma4
- 穩定可用 context：`4096`
- 4096: ok
- 8192: fail
- 12288: fail
- 16384: fail

## codellama
- 穩定可用 context：`未完成`
- 4096: fail
- 8192: fail
- 12288: fail
- 16384: fail
