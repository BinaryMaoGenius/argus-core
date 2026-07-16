import types

import pytest

from app.model_adapter import OllamaModelProvider


class DummyResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


def test_get_loaded_models_monkeypatched(monkeypatch):
    provider = OllamaModelProvider(base_url="http://localhost:11434")

    def fake_get(url, timeout=5):
        assert url.endswith("/api/ps")
        return DummyResp({"models": [{"name": "qwen2.5:0.5b"}]})

    monkeypatch.setattr("requests.get", fake_get)
    loaded = provider.get_loaded_models()
    assert isinstance(loaded, list)
    assert "qwen2.5:0.5b" in loaded
