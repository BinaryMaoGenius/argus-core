# -*- coding: utf-8 -*-
"""
Test live COS + Ollama (sans mock).
Modeles : qwen2.5:0.5b (FAST) + qwen2.5-coder:7b (SLOW)

Lancer le serveur COS avant ce script :
    .venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

Usage :
    .venv\\Scripts\\python.exe scripts/test_live_ollama.py
"""

import io
import json
import sys
import time
import requests

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MODEL_FAST_TEST = "qwen2.5:0.5b"
MODEL_SLOW_TEST = "qwen2.5-coder:7b"

BASE   = "http://127.0.0.1:8000"
OLLAMA = "http://localhost:11434"

passed = 0
failed = 0


def ok(label, detail=""):
    global passed
    passed += 1
    suffix = f"  =>  {detail}" if detail else ""
    print(f"  [PASS]  {label}{suffix}")


def fail(label, detail=""):
    global failed
    failed += 1
    suffix = f"  =>  {detail}" if detail else ""
    print(f"  [FAIL]  {label}{suffix}")


def section(title):
    print(f"\n{'='*62}")
    print(f"  {title}")
    print(f"{'='*62}")


# ==============================================================
# 1. Sanity checks
# ==============================================================
section("1. SANITY CHECKS (sans LLM)")

try:
    r = requests.get(f"{BASE}/ping", timeout=5)
    if r.status_code == 200 and r.json().get("status") == "ok":
        ok("COS /ping", str(r.json()))
    else:
        fail("COS /ping", r.text)
except Exception as e:
    fail("COS /ping -- serveur non demarre ?", str(e))
    print("\n[!] Le serveur COS n'est pas lance. Demarre-le avec :")
    print("    .venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000")
    sys.exit(1)

try:
    r = requests.get(f"{OLLAMA}/api/ps", timeout=5)
    models_loaded = [m["name"] for m in r.json().get("models", [])]
    ok("Ollama /api/ps", f"modeles en memoire : {models_loaded or 'aucun (chargement a la demande)'}")
except Exception as e:
    fail("Ollama non joignable", str(e))


# ==============================================================
# 2. Routeur deterministe
# ==============================================================
section("2. ROUTEUR DETERMINISTE")

routing_tests = [
    ("bonjour",                                          "fast", "salutation courte -> fast"),
    ("a" * 200,                                          "slow", "prompt long 200 chars -> slow"),
    ("ecris un script Python pour lire un fichier CSV",  "slow", "mot-cle complexe (ecris/fichier) -> slow"),
    ("merci",                                            "fast", "merci -> fast"),
    ("",                                                 "fast", "prompt vide -> fast"),
]

for prompt, expected_path, label in routing_tests:
    try:
        r = requests.post(f"{BASE}/decide", params={"prompt": prompt}, timeout=5)
        body = r.json()
        if body["path"] == expected_path:
            ok(label, f"path={body['path']}  model={body['model']}  reason={body['reason']}")
        else:
            fail(label, f"attendu={expected_path}  obtenu={body['path']}  reason={body['reason']}")
    except Exception as e:
        fail(label, str(e))


# ==============================================================
# 3. Memoire
# ==============================================================
section("3. MEMOIRE")

try:
    r = requests.post(
        f"{BASE}/memory/write",
        json={"text": "Python os.listdir pour lister les fichiers", "layer": "working"},
        timeout=5,
    )
    assert r.status_code == 200 and r.json().get("ok")
    ok("Ecriture memoire working")
except Exception as e:
    fail("Ecriture memoire working", str(e))

try:
    r = requests.get(f"{BASE}/memory/recall", params={"q": "lister fichiers", "top_k": 3}, timeout=5)
    results = r.json()["results"]
    assert len(results) > 0
    ok("Recall memoire", f"{len(results)} resultat(s) retourne(s)")
except Exception as e:
    fail("Recall memoire", str(e))


# ==============================================================
# 4. Generation LLM -- FAST PATH (0.5b)
# ==============================================================
section(f"4. GENERATION REELLE -- FAST PATH ({MODEL_FAST_TEST})")

PROMPT_FAST = "Quelle est la syntaxe Python pour afficher hello world ?"
print(f"  Prompt : {PROMPT_FAST}")
print("  Attente de la reponse (streaming)...")

try:
    r = requests.post(
        f"{BASE}/generate/stream",
        json={"prompt": PROMPT_FAST, "model": MODEL_FAST_TEST, "num_predict": 60},
        stream=True,
        timeout=120,
    )
    r.raise_for_status()

    routing_info = None
    response_text = ""
    metrics = None

    for line in r.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        if chunk.get("type") == "routing":
            routing_info = chunk
        elif chunk.get("type") == "metrics":
            metrics = chunk
        elif chunk.get("response"):
            response_text += chunk["response"]

    if routing_info:
        ok("Routing detecte", f"path={routing_info['path']}  model={routing_info['model']}")
    if response_text:
        preview = response_text[:120].replace("\n", " ")
        ok(f"Reponse recue ({len(response_text)} chars)", f'"{preview}"')
    else:
        fail("Aucune reponse texte recue")

    if metrics:
        ok(
            "Metriques fast",
            f"1er token={metrics.get('time_to_first_token_s')}s  "
            f"total={metrics.get('total_time_s')}s  "
            f"tokens~{metrics.get('approx_tokens')}",
        )

except Exception as e:
    fail("Generation streaming fast path", str(e))


# ==============================================================
# 5. Generation LLM -- SLOW PATH (7b)
# ==============================================================
section(f"5. GENERATION REELLE -- SLOW PATH ({MODEL_SLOW_TEST})")

PROMPT_SLOW = "Ecris un script Python pour lire un fichier CSV et afficher les 5 premieres lignes."
print(f"  Prompt : {PROMPT_SLOW}")
print("  Attente de la reponse (peut prendre 30-120 sec sur CPU)...")
print()

try:
    r = requests.post(
        f"{BASE}/generate/stream",
        json={"prompt": PROMPT_SLOW, "model": MODEL_SLOW_TEST, "num_predict": 150},
        stream=True,
        timeout=300,
    )
    r.raise_for_status()

    routing_info = None
    response_text = ""
    metrics = None

    for line in r.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        if chunk.get("type") == "routing":
            routing_info = chunk
            print(f"  [routing] path={routing_info['path']}  model={routing_info['model']}")
        elif chunk.get("type") == "metrics":
            metrics = chunk
        elif chunk.get("response"):
            response_text += chunk["response"]
            print(chunk["response"], end="", flush=True)

    print()

    if routing_info:
        ok("Routing detecte", f"path={routing_info['path']}  model={routing_info['model']}")
    if response_text:
        ok(f"Reponse recue ({len(response_text)} chars)")
    else:
        fail("Aucune reponse texte recue")

    if metrics:
        ok(
            "Metriques slow",
            f"1er token={metrics.get('time_to_first_token_s')}s  "
            f"total={metrics.get('total_time_s')}s  "
            f"tokens~{metrics.get('approx_tokens')}",
        )

except Exception as e:
    fail("Generation streaming slow path", str(e))


# ==============================================================
# Resume
# ==============================================================
section("RESUME FINAL")
total = passed + failed
status = "OK" if failed == 0 else "ECHEC"
print(f"  [{status}]  {passed}/{total} tests passes  ({failed} echec(s))\n")
sys.exit(0 if failed == 0 else 1)
