"""Model adapter abstractions and a minimal Ollama provider."""
from typing import Dict, Any, List, Iterator, Optional
import json
import requests
import difflib
from .logging import get_logger, struct_log

_logger = get_logger("model_adapter")


class ModelProvider:
    """Abstract model provider interface."""

    def get_loaded_models(self) -> List[str]:
        raise NotImplementedError()

    def generate(self, model: str, prompt: str, num_predict: int) -> Dict[str, Any]:
        raise NotImplementedError()

    def stream_generate(self, model: str, prompt: str, num_predict: int, keep_alive: str = "10m") -> Iterator[Dict[str, Any]]:
        raise NotImplementedError()


class OllamaModelProvider(ModelProvider):
    def __init__(self, base_url: str = "http://localhost:11434", cache_enabled: bool = True, cache_threshold: float = 0.9):
        self.base_url = base_url.rstrip("/")
        self.cache_enabled = cache_enabled
        self.cache_threshold = cache_threshold
        self._cache: List[Dict[str, Any]] = []  # list of {prompt, response}

    def _semantic_get(self, prompt: str) -> Optional[Dict[str, Any]]:
        if not self.cache_enabled:
            return None
        # naive similarity search
        best = None
        best_ratio = 0.0
        for entry in self._cache:
            r = difflib.SequenceMatcher(a=prompt, b=entry["prompt"]).ratio()
            if r > best_ratio:
                best_ratio = r
                best = entry
        if best and best_ratio >= self.cache_threshold:
            struct_log(_logger, "info", event="cache_hit", ratio=best_ratio, prompt=prompt)
            return best["response"]
        return None

    def _semantic_set(self, prompt: str, response: Dict[str, Any]) -> None:
        if not self.cache_enabled:
            return
        self._cache.append({"prompt": prompt, "response": response})

    def get_loaded_models(self) -> List[str]:
        try:
            resp = requests.get(f"{self.base_url}/api/ps", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def _resolve_model(self, model: str) -> str:
        loaded = self.get_loaded_models()
        if not loaded:
            return model
        if model in loaded:
            return model

        base = model.split(":")[0]
        family = [m for m in loaded if m.startswith(base)]
        if family:
            struct_log(_logger, "warning", event="model_fallback_family", requested=model, chosen=family[0])
            return family[0]

        preferred = ["qwen2.5:14b", "qwen2.5-coder:7b", "qwen2.5:7b", "qwen2.5:0.5b"]
        for candidate in preferred:
            if candidate in loaded:
                struct_log(_logger, "warning", event="model_fallback_preferred", requested=model, chosen=candidate)
                return candidate

        struct_log(_logger, "warning", event="model_fallback_default", requested=model, chosen=loaded[0])
        return loaded[0]

    def generate(self, model: str, prompt: str, num_predict: int = 50, keep_alive: str = "10m", response_format: str = None) -> Dict[str, Any]:
        model = self._resolve_model(model)
        # Semantic cache check
        cached = self._semantic_get(prompt)
        if cached is not None:
            struct_log(_logger, "info", event="generate_cache_return", model=model, num_predict=num_predict)
            return cached
        # Semantic cache check
        cached = self._semantic_get(prompt)
        if cached is not None:
            struct_log(_logger, "info", event="generate_cache_return", model=model, num_predict=num_predict)
            return cached

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": keep_alive,
            "options": {"num_predict": num_predict},
        }
        if response_format:
            payload["format"] = response_format
            
        struct_log(_logger, "info", event="generate_call", model=model, num_predict=num_predict, format=response_format)
        resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        # store in semantic cache
        self._semantic_set(prompt, data)
        struct_log(_logger, "info", event="generate_store_cache", model=model)
        return data

    def stream_generate(self, model: str, prompt: str, num_predict: int = 50, keep_alive: str = "10m", response_format: str = None) -> Iterator[Dict[str, Any]]:
        """Stream response from Ollama `/api/generate` and yield parsed chunks.

        Yields JSON-parsed lines as dicts (same format as in `bench.py`).
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "keep_alive": keep_alive,
            "options": {"num_predict": num_predict},
        }
        if response_format:
            payload["format"] = response_format
            
        struct_log(_logger, "info", event="stream_generate_call", model=model, num_predict=num_predict, keep_alive=keep_alive, format=response_format)

        t_start = None
        t_first_token = None
        token_count = 0

        with requests.post(f"{self.base_url}/api/generate", json=payload, stream=True, timeout=180) as resp:
            resp.raise_for_status()
            t_start = __import__("time").perf_counter()
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except Exception:
                    continue
                # detect first token based on presence of 'response' or 'token' fields
                if t_first_token is None and chunk.get("response"):
                    t_first_token = __import__("time").perf_counter()
                if chunk.get("response"):
                    token_count += 1
                yield chunk
            t_end = __import__("time").perf_counter()

        # After streaming, log telemetry
        telemetry = {
            "event": "stream_generate_telemetry",
            "model": model,
            "num_predict": num_predict,
            "time_to_first_token_s": round(t_first_token - t_start, 3) if (t_first_token and t_start) else None,
            "total_time_s": round(t_end - t_start, 3) if t_start else None,
            "approx_tokens": token_count,
        }
        struct_log(_logger, "info", **telemetry)

