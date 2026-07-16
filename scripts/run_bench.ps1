Param()

Write-Host "Running COS benchmark runner..."

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Warning: 'ollama' not found in PATH. Ensure Ollama is installed and 'ollama serve' is running." -ForegroundColor Yellow
}

$env:OLLAMA_MAX_LOADED_MODELS = "2"
python -u .\bench_runner.py
