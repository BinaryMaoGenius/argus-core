# Benchmarks — Reproducible runs

Purpose
-------
Provide a reproducible local benchmark workflow for measuring Ollama latencies and validating fast/slow path behaviour.

Prerequisites
-------------
- Ollama installed and running locally (`ollama serve`).
- Set `OLLAMA_MAX_LOADED_MODELS=2` in the same shell where you start Ollama, or use the provided runner which sets it.

Quick run (PowerShell)
-----------------------
```powershell
# start Ollama in the same terminal (if not already running):
$env:OLLAMA_MAX_LOADED_MODELS="2"
ollama serve

# in another terminal (repo root):
python bench_runner.py
# or via helper
.\scripts\run_bench.ps1
```

Output
------
- `benchmark_results_v2.json` — JSON file with timings produced by `bench.py`.

Notes
-----
- The runner checks that Ollama is reachable at `http://localhost:11434` before launching the benchmark.
- CI runs are not included by default because Ollama is an external dependency; consider adding an integration job that targets a self-hosted runner with Ollama installed.
