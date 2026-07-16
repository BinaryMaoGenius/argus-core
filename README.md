# COS — Cognitive Operating System

> Un noyau cognitif local-first, modulaire et indépendant du modèle, conçu pour tourner sur du matériel contraint (CPU, sans GPU dédié).

## Pourquoi ce projet

La plupart des frameworks d'agents sont pensés pour le cloud avec GPU. Ce projet part d'une contrainte inverse : faire tourner un système cognitif complet — mémoire, planification, vérification, apprentissage sans fine-tuning — sur un poste local, avec un cas d'usage réel ancré dans le contexte malien (assistant financier WhatsApp, traduction Bambara, outils pour développeurs).

Le projet ne cherche pas à réinventer ce qui existe déjà ; il compose avec des briques connues et concentre l'effort sur ce qui manque encore : l'optimisation du chemin critique sur CPU local, avec des budgets de latence mesurés.

## État actuel

**v0.1 MVP en cours.** Voir [ROADMAP.md](./ROADMAP.md) pour les jalons et [CAHIER_DES_CHARGES.md](./CAHIER_DES_CHARGES.md) pour la spécification complète.

## Prérequis

- Python 3.10+
- [Ollama](https://ollama.com) installé et démarré
- Modèles Ollama recommandés :

```powershell
ollama pull qwen2.5:7b
ollama pull qwen2.5:14b
```

## Installation rapide (Windows)

```powershell
cd "c:\Users\USER\Desktop\ARGUS Core"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Démarrage du serveur

```powershell
cd "c:\Users\USER\Desktop\ARGUS Core"
.\.venv\Scripts\Activate.ps1
python -m app.main
```

Le serveur démarre alors sur http://localhost:8000.

## Démo MVP

### 1) Démo locale sans Ollama

```powershell
cd "c:\Users\USER\Desktop\ARGUS Core"
.\.venv\Scripts\Activate.ps1
python -m app.demo_flow --prompt "Explain how to list files in Python" --mock
```

### 2) Exemple d'appel API

```powershell
curl -X POST "http://localhost:8000/memory/write" -H "Content-Type: application/json" -d "{\"text\":\"List files in Python using os.listdir\",\"layer\":\"working\"}"
```

```powershell
curl "http://localhost:8000/memory/recall?q=list%20files&top_k=5"
```

```powershell
curl -X POST "http://localhost:8000/generate" -H "Content-Type: application/json" -d "{\"prompt\":\"Bonjour\",\"model\":\"qwen2.5:14b\"}"
```

## Tests

```powershell
cd "c:\Users\USER\Desktop\ARGUS Core"
.\.venv\Scripts\Activate.ps1
pytest -q
```

## Principes de design

- Local-first : pas de dépendance cloud obligatoire.
- Indépendance au modèle : le routeur peut choisir un modèle adapté sans verrouiller le système à un seul fournisseur.
- Chemin critique in-process : pas d’event bus ni de microservices tant que la mesure ne l’exige pas.
- Budgets de latence mesurés, pas supposés.
- Pas de fine-tuning local : l’amélioration passe par l’ingénierie de contexte.

## Structure du dépôt

```text
cos/
├── app/
│   ├── main.py              # API FastAPI
│   ├── model_adapter.py     # Interface ModelProvider (Ollama)
│   ├── router.py            # Triage règles → 0.5B → 7B
│   ├── memory/              # Working / Recall / Archival
│   ├── engines/             # Planning, Reasoning, Verification, ...
│   └── tools/               # Plugins d’outils (MCP-compatible)
├── tests/
├── CAHIER_DES_CHARGES.md
├── ROADMAP.md
└── README.md
```

## Licence

À définir avant la v0.2 (open source visé, MIT ou Apache 2.0).
