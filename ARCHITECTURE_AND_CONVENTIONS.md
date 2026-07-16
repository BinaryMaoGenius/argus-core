# Architecture & Conventions — COS (v0.5)

Objectif
-------
Documenter les conventions et contrats d'interface pour la nouvelle architecture "Low-Tech / High-IQ" du projet COS (v0.5+), afin d'assurer cohérence, testabilité et hyper-optimisation sur CPU.

Principes Fondateurs (Low-Tech / High-IQ)
---------------------------------------
- **Local-first** : Aucune dépendance cloud. Exécution sur CPU avec contraintes de RAM.
- **Routage Déterministe (Fast Path)** : Ne pas réveiller un LLM pour des tâches simples. Utilisation de Regex et heuristiques en millisecondes.
- **Prefix-Stable Caching** : Structure de prompt gelée (System + Historique en tête) pour maximiser le Time-To-First-Token (TTFT) via le KV-Cache.
- **Grammar Constrained Decoding** : Format GBNF / JSON forcé côté moteur pour garantir des plans stricts sans erreur de parsing.
- **Skeleton-of-Thought** : Le LLM ne perd pas de tokens à s'expliquer. Il produit des listes JSON de commandes brutes (le squelette).
- **Parallélisation (Async)** : Le moteur d'exécution regroupe les tâches indépendantes via `asyncio` pour supprimer les temps d'attente système.

Structure de code (Mise à jour v0.5)
------------------------------------
- `app/` : coeur de l'application.
  - `main.py` : API Gateway FastAPI. Construit le prompt `Prefix-Stable`.
  - `model_adapter.py` : Interface `ModelProvider` gérant Ollama avec paramètre `format="json"` pour le GBNF.
  - `router.py` : Triage ultra-rapide par heuristiques Python (Regex).
  - `security.py` : `SecurityEngine` imposant le mode "Dry-Run" humain pour les effets de bord.
  - `memory/`
    - `memory.py` : `MemoryKernel` à trois couches (Working, Recall, Archival) avec module d'apprentissage Few-Shot (`get_similar_plans`).
  - `engines/`
    - `planning.py` : `PlanningEngine` utilisant l'approche *Skeleton-of-Thought* et le Few-Shot dynamique.
    - `execution.py` : `ExecutionEngine` asynchrone gérant la parallélisation des tâches.
  - `tools/`
    - `registry.py` : Enregistrement des plugins.
    - `tool_engine.py` : Chef d'orchestre des outils avec barrière `SecurityEngine`.
    - `fs_tools.py` : Outils primaires (read_file, write_file).
    - `macro_tools.py` : Outils combinés (ex: `search_and_replace`) évitant les allers-retours coûteux avec le LLM.

Conventions d'interface
-----------------------
- **ModelProvider** (abstrait)
  - Doit supporter le paramètre `response_format` (ex: "json") pour le GBNF.
  - `generate(..., response_format: str = None)`
  - `stream_generate(...)`

- **PlanningEngine**
  - Prompt strict demandant un tableau JSON de tâches (`{"id", "type", "tool", "cmd", "async_group"}`).
  - Injecte les succès passés de l'Archival memory.

- **AsyncExecutionEngine**
  - Fonctionne de manière asynchrone (`async def`).
  - Regroupe l'exécution des outils/shells par la clé `async_group` via `asyncio.gather`.

- **Macro-Tools**
  - Les outils doivent encapsuler un maximum de logique métier Python pour limiter les boucles de raisonnement du LLM.

Flow cognitif (Tâches Complexes)
--------------------------------
1. Requête reçue par `main.py`.
2. `Router` détecte un mot clé complexe (Regex) → Route vers 7B.
3. `main.py` ajoute la Working Memory en mode **Prefix-Stable**.
4. Le `PlanningEngine` recherche des plans similaires réussis (Few-Shot).
5. Le `PlanningEngine` interroge Ollama avec `format="json"`.
6. Le modèle génère très rapidement un tableau JSON d'étapes (Skeleton-of-Thought).
7. Le `AsyncExecutionEngine` lit le plan et lance en parallèle les tâches de même groupe.
8. Avant chaque outil/shell, le `SecurityEngine` valide l'action (Dry-Run).
9. Retour du résultat à l'utilisateur et sauvegarde du contexte en Working Memory.

Testing et CI
--------------
- Tests unitaires: `pytest`.
- Tester en priorité les heuristiques du `Router` et les `Macro-Tools`.
- Pour les tests d'inférence avec LLM, utiliser des mocks asynchrones.

Opérations locales
------------------
Lancer l'API locale avec rechargement :
```powershell
python -m uvicorn app.main:app --reload
```
