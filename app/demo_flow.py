"""Demo flow: Router -> MemoryKernel -> ModelAdapter.

Usage:
  python -m app.demo_flow --prompt "Explain X" [--mock]

If `--mock` is set, a local mock model provider is used to avoid requiring Ollama.
"""
import argparse
import time
from typing import Iterator, Dict, Any

from .router import route_decide
from .memory.memory import MemoryKernel
from .model_adapter import OllamaModelProvider, ModelProvider
from .logging import get_logger, struct_log

logger = get_logger("demo_flow")


class MockModelProvider(ModelProvider):
    def generate(self, model: str, prompt: str, num_predict: int = 50, keep_alive: str = "10m") -> Dict[str, Any]:
        # deterministic fake response
        time.sleep(0.1)
        return {"response": f"MOCK response for model={model}; prompt={prompt[:80]}", "done": True}

    def stream_generate(self, model: str, prompt: str, num_predict: int = 50, keep_alive: str = "10m") -> Iterator[Dict[str, Any]]:
        # yield token-like chunks
        for i in range(min(5, num_predict)):
            time.sleep(0.05)
            yield {"response": f"token_{i}", "done": False}
        yield {"response": "<end>", "done": True}


def enrich_prompt_with_memory(prompt: str, mem: MemoryKernel, k: int = 3) -> str:
    tops = mem.recall_top(prompt, top_k=k)
    if not tops:
        return prompt
    snippets = [f"[{t['layer']}]: {t['item'].get('text')[:200]}" for t in tops]
    enriched = "\n".join(snippets) + "\n\n" + prompt
    struct_log(logger, "info", event="enrich_prompt", added=len(snippets))
    return enriched


def stream_print(provider: ModelProvider, model: str, prompt: str, num_predict: int = 50):
    t_start = time.perf_counter()
    t_first = None
    token_count = 0
    for chunk in provider.stream_generate(model, prompt, num_predict=num_predict):
        if t_first is None and chunk.get("response"):
            t_first = time.perf_counter()
        if chunk.get("response"):
            token_count += 1
            print(chunk.get("response"), end=" ", flush=True)
        if chunk.get("done"):
            break
    t_end = time.perf_counter()
    print()
    telemetry = {
        "event": "demo_flow_generate_telemetry",
        "model": model,
        "time_to_first_token_s": round(t_first - t_start, 3) if (t_first and t_start) else None,
        "total_time_s": round(t_end - t_start, 3),
        "approx_tokens": token_count,
    }
    struct_log(logger, "info", **telemetry)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--model", default="qwen2.5-coder:7b")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--num_predict", type=int, default=80)
    args = parser.parse_args()

    mem = MemoryKernel()
    # seed working memory with an example
    mem.write({"text": "Example: list files in Python with os.listdir"}, layer="working")

    provider = MockModelProvider() if args.mock else OllamaModelProvider()

    model_choice = route_decide(args.prompt)
    struct_log(logger, "info", event="route_decide", chosen=model_choice)

    enriched = enrich_prompt_with_memory(args.prompt, mem, k=3)

    stream_print(provider, args.model, enriched, num_predict=args.num_predict)


if __name__ == "__main__":
    main()
