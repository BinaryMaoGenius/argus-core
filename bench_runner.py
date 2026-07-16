"""Runner for reproducible local benchmarks using bench.py.

Features:
- checks Ollama service availability
- sets `OLLAMA_MAX_LOADED_MODELS` env var if not set
- runs `bench.py` and ensures `benchmark_results_v2.json` is produced
- exits with non-zero code if checks fail

Usage:
    python bench_runner.py

Note: Ollama must be installed and reachable at http://localhost:11434.
"""
import os
import sys
import time
import requests
import subprocess

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
RESULT_FILE = "benchmark_results_v2.json"


def check_ollama():
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/ps", timeout=5)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"Ollama not available at {OLLAMA_URL}: {e}")
        return False


def ensure_env():
    if not os.environ.get("OLLAMA_MAX_LOADED_MODELS"):
        os.environ["OLLAMA_MAX_LOADED_MODELS"] = "2"
        print("Set OLLAMA_MAX_LOADED_MODELS=2 for benchmark run")


def run_bench():
    print("Running bench.py...")
    # run bench.py in subprocess to ensure env var is effective
    try:
        subprocess.check_call([sys.executable, "bench.py"], env=os.environ)
    except subprocess.CalledProcessError as e:
        print("bench.py failed:", e)
        return False
    if not os.path.exists(RESULT_FILE):
        print(f"Expected result file {RESULT_FILE} not found")
        return False
    print(f"Bench finished, results in {RESULT_FILE}")
    return True


def main():
    print("Bench runner starting")
    ensure_env()
    if not check_ollama():
        print("Please start Ollama with the environment variable set, e.g.:")
        print("  $env:OLLAMA_MAX_LOADED_MODELS=\"2\"; ollama serve")
        sys.exit(2)

    ok = run_bench()
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
