"""
Banc de mesure de latence Ollama — COS project — v2
======================================================

Corrections vs v1 :
  1. num_predict fixé pour chaque test (comparaisons valides, triage réellement court)
  2. Vérification explicite de la résidence simultanée des modèles (/api/ps)
     + mesure du coût de bascule triage <-> exécution
  3. Test de préfixe stable à SORTIE CONTRÔLÉE (même num_predict des deux côtés)

Avant de lancer ce script, dans le MÊME terminal (important, la variable ne
s'applique qu'au process où elle est définie) :

    # PowerShell :
    $env:OLLAMA_MAX_LOADED_MODELS="2"
    ollama serve

    # Si Ollama tourne déjà en tâche de fond (icône barre des tâches),
    # ferme-le d'abord (clic droit -> Quit), puis relance-le depuis un
    # terminal où la variable est définie, OU définis la variable au
    # niveau système (Paramètres Windows -> Variables d'environnement)
    # et redémarre le service Ollama pour qu'elle soit prise en compte.

Utilisation :
    pip install requests
    python benchmark_ollama_v2.py
"""

import json
import time
import statistics
from datetime import datetime

import requests

OLLAMA_URL = "http://localhost:11434"

MODELS = {
    "triage_7b": "qwen2.5:7b",
    "coder_14b": "qwen2.5:14b",
}

TEST_PROMPTS = {
    "trivial": "Quelle est la syntaxe pour lister les fichiers en Python ?",
    "debug_django": (
        "J'ai une erreur 'IntegrityError' sur un modèle Django avec une "
        "ForeignKey nullable. Comment je débugue ça rapidement ?"
    ),
    "complexe_multi_etapes": (
        "Explique-moi comment structurer un endpoint DRF qui reçoit un "
        "fichier audio, le transcrit via une API externe, et stocke le "
        "résultat en base avec un statut de traitement asynchrone."
    ),
}

STABLE_PREFIX = (
    "Tu es un assistant technique expert en Python, Django et systèmes "
    "distribués. Réponds de façon concise et actionnable.\n\n"
)

# Longueur de sortie fixée par contexte de test — condition indispensable
# pour que les comparaisons de temps soient valides.
NUM_PREDICT_TRIAGE = 20        # le triage doit répondre en quelques mots
NUM_PREDICT_SHORT = 80         # réponse courte contrôlée (test préfixe)
NUM_PREDICT_NORMAL = 300       # réponse "normale" bornée pour fast/slow path


def get_loaded_models() -> list[str]:
    """Interroge /api/ps pour voir quels modèles sont actuellement en mémoire."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/ps", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        return [f"erreur: {e}"]


def call_ollama_stream(model: str, prompt: str, num_predict: int, keep_alive: str = "10m") -> dict:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "keep_alive": keep_alive,
        "options": {"num_predict": num_predict},
    }

    t_start = time.perf_counter()
    t_first_token = None
    token_count = 0

    with requests.post(
        f"{OLLAMA_URL}/api/generate", json=payload, stream=True, timeout=180
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            if t_first_token is None and chunk.get("response"):
                t_first_token = time.perf_counter()
            if chunk.get("response"):
                token_count += 1
            if chunk.get("done"):
                t_end = time.perf_counter()
                break
        else:
            t_end = time.perf_counter()

    return {
        "time_to_first_token_s": (
            round(t_first_token - t_start, 3) if t_first_token else None
        ),
        "total_time_s": round(t_end - t_start, 3),
        "approx_tokens": token_count,
    }


def run_suite(label: str, model: str, prompt: str, num_predict: int, repeats: int = 3):
    print(f"\n--- {label} | modèle={model} | num_predict={num_predict} | répétitions={repeats} ---")
    results = []
    for i in range(repeats):
        r = call_ollama_stream(model, prompt, num_predict=num_predict)
        print(
            f"  run {i+1}: first_token={r['time_to_first_token_s']}s "
            f"total={r['total_time_s']}s tokens={r['approx_tokens']}"
        )
        results.append(r)
    return results


def summarize(results: list[dict]) -> dict:
    first_tokens = [r["time_to_first_token_s"] for r in results if r["time_to_first_token_s"]]
    totals = [r["total_time_s"] for r in results]
    return {
        "mean_time_to_first_token_s": round(statistics.mean(first_tokens), 3) if first_tokens else None,
        "mean_total_time_s": round(statistics.mean(totals), 3),
        "min_total_time_s": round(min(totals), 3),
        "max_total_time_s": round(max(totals), 3),
    }


def main():
    all_results = {"timestamp": datetime.now().isoformat(), "tests": {}}

    print("Modèles actuellement chargés en mémoire :", get_loaded_models())

    # 1) Triage réellement court (num_predict bas) — le vrai test cette fois
    print("\n========== TEST 1 : Triage 7B avec sortie courte contrôlée ==========")
    for prompt_label, prompt_text in TEST_PROMPTS.items():
        key = f"triage_7b__{prompt_label}"
        results = run_suite(key, MODELS["triage_7b"], prompt_text, NUM_PREDICT_TRIAGE)
        all_results["tests"][key] = {"runs": results, "summary": summarize(results)}

    print("\n========== TEST 2 : 14B coder avec sortie normale bornée (300 tokens max) ==========")
    for prompt_label, prompt_text in TEST_PROMPTS.items():
        key = f"coder_14b__{prompt_label}"
        results = run_suite(key, MODELS["coder_14b"], prompt_text, NUM_PREDICT_NORMAL)
        all_results["tests"][key] = {"runs": results, "summary": summarize(results)}

    # 3) Résidence simultanée : bascule triage -> exécution -> triage
    print("\n========== TEST 3 : coût de bascule entre modèles (résidence simultanée ?) ==========")
    print("Modèles chargés avant bascule :", get_loaded_models())

    switch_results = []
    sequence = [
        ("triage_7b", MODELS["triage_7b"], NUM_PREDICT_TRIAGE),
        ("coder_14b", MODELS["coder_14b"], NUM_PREDICT_SHORT),
        ("triage_7b", MODELS["triage_7b"], NUM_PREDICT_TRIAGE),
        ("coder_14b", MODELS["coder_14b"], NUM_PREDICT_SHORT),
    ]
    for label, model_name, num_pred in sequence:
        r = call_ollama_stream(model_name, TEST_PROMPTS["trivial"], num_predict=num_pred)
        loaded = get_loaded_models()
        print(f"  appel {label}: first_token={r['time_to_first_token_s']}s total={r['total_time_s']}s | chargés={loaded}")
        switch_results.append({"model": label, **r, "loaded_models_after": loaded})

    all_results["tests"]["model_switch_cost"] = switch_results

    # 4) Préfixe stable à sortie strictement contrôlée (même num_predict)
    print("\n========== TEST 4 : effet du préfixe stable, sortie contrôlée (80 tokens fixes) ==========")
    p1 = call_ollama_stream(
        MODELS["coder_14b"],
        STABLE_PREFIX + "Résume en une phrase ce qu'est une ForeignKey.",
        num_predict=NUM_PREDICT_SHORT,
    )
    p2 = call_ollama_stream(
        MODELS["coder_14b"],
        STABLE_PREFIX + "Résume en une phrase ce qu'est un middleware Django.",
        num_predict=NUM_PREDICT_SHORT,
    )
    print(f"  appel 1 (préfixe stable + question A): {p1}")
    print(f"  appel 2 (préfixe stable + question B): {p2}")
    all_results["tests"]["stable_prefix_effect_v2"] = {"call_1": p1, "call_2": p2}

    with open("benchmark_results_v2.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print("\n=== Résultats complets écrits dans benchmark_results_v2.json ===")
    print("\nRésumé rapide :")
    for key, val in all_results["tests"].items():
        if isinstance(val, dict) and "summary" in val:
            s = val["summary"]
            print(f"  {key}: 1er token ~{s['mean_time_to_first_token_s']}s | total ~{s['mean_total_time_s']}s")


if __name__ == "__main__":
    main()
