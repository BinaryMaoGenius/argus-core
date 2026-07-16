# Roadmap — Cognitive Operating System (COS)

> Règle directrice : chaque version doit être **utilisée** avant de passer à la suivante, pas seulement codée. Le risque principal identifié dans le cahier des charges est l'épuisement avant la première version utile — cette roadmap est volontairement découpée fin pour forcer des jalons courts et vérifiables.

---

## v0.1 — Kernel minimal, chemin critique seul

**Objectif** : un chat CLI qui répond, garde le contexte d'une session, et route intelligemment entre modèle léger et modèle lourd — avec des temps de réponse dans les budgets mesurés.

- [x] Benchmark de latence sur la machine cible (`benchmark_ollama.py`, `benchmark_ollama_v2.py`)
- [x] Validation de la résidence simultanée des deux modèles (`OLLAMA_MAX_LOADED_MODELS=2`)
- [ ] `ModelProvider` : interface abstraite + implémentation Ollama (appel streaming, `num_predict` paramétrable, `keep_alive` configuré)
- [ ] `Router` : règles (regex actions destructrices, longueur de requête) → 0.5B (`num_predict` ≈ 20) → décision fast/slow
- [ ] `ReasoningEngine` minimal : un seul appel structuré au 7B pour le slow path (pas encore de décomposition multi-étapes)
- [ ] Working Memory : liste des N derniers tours en mémoire process (pas de persistance)
- [ ] CLI simple (`app/main.py`) avec sortie streamée token par token
- [ ] Tests de contrat sur `Router` et `ModelProvider` avec mock (sans dépendre d'Ollama pour les tests unitaires)
- [ ] Critère de sortie : fast path mesuré entre 3 et 6s sur 10 requêtes types ; slow path streamé et utilisable même si le total dépasse 30s

## v0.2 — Mémoire persistante + premier outil réel

**Objectif** : le système se souvient d'une session à l'autre et peut agir sur le système de fichiers.

- [ ] PostgreSQL + pgvector : schéma pour Recall Memory et mémoire de projet
- [ ] `MemoryEngine.recall()` / `.write()` : interface unique cachant working/recall/archival
- [ ] Cache sémantique de requêtes (évite un appel LLM si une question quasi-identique a déjà une réponse en mémoire)
- [ ] Premier outil réel via `ToolEngine` : lecture/écriture de fichiers, avec confirmation obligatoire pour l'écriture
- [ ] `SecurityEngine` v0 : liste blanche de commandes, mode dry-run par défaut pour toute action destructrice
- [ ] Structure de prompt à préfixe stable (system + contexte quasi-stable en tête, requête variable en fin) pour maximiser la réutilisation du KV-cache Ollama
- [ ] Décision : licence du projet (MIT vs Apache 2.0)

## v0.5 — Planification + vérification supervisées

**Objectif** : le système décompose un objectif complexe et demande validation humaine avant d'exécuter.

- [ ] `PlanningEngine` : décomposition simple d'un objectif en sous-tâches ordonnées (sans boucle de révision complexe)
- [ ] `VerificationEngine` : production d'un "belief record" (connu / inféré / supposé / confiance / sources / non-vérifié) avant toute exécution
- [ ] Cycle cognitif complet activé, mais en **mode supervisé** : chaque plan est affiché et validé par l'humain avant exécution
- [ ] Intégration MCP pour au moins deux outils supplémentaires (ex : Git, terminal sandboxé)
- [ ] Premier test réel sur un cas d'usage BMG concret (ex : scraper, tâche Wari Agent)
- [ ] Mesure : taux de plans validés sans modification par l'humain (indicateur de qualité du Planning Engine)

## v1.0 — Boucle autonome supervisée + apprentissage niveau 1

**Objectif** : le système exécute des tâches multi-étapes sans validation à chaque étape, avec des points de contrôle configurables.

- [ ] `ExecutionEngine` : orchestration d'un plan multi-étapes avec gestion d'échec (retry, escalade humaine)
- [ ] `ReflectionEngine` : post-mortem structuré après chaque exécution (succès/échec, cause probable)
- [ ] `LearningEngine` niveau 1 : bibliothèque de plans réussis réutilisée comme few-shot dans le Planning Engine
- [ ] Points de contrôle configurables (l'humain choisit le niveau d'autonomie par type de tâche)
- [ ] Background path : worker isolé pour la consolidation mémoire, **seulement si un benchmark montre une dégradation du chemin critique sans isolation**
- [ ] Premier document de leçons apprises sur l'écart entre l'architecture prévue et l'usage réel (revue du cahier des charges)

## v2.0 — Multi-modèle + Knowledge Engine

**Objectif** : prouver l'indépendance au modèle et enrichir la base de connaissances.

- [ ] `ModelProvider` étendu : au moins un second backend (API distante ou autre runtime local) en plus d'Ollama, sans modification du kernel
- [ ] `KnowledgeEngine` : RAG documentaire complet sur pgvector
- [ ] Évaluation du besoin réel d'un graphe temporel (Graphiti) — décision prise sur preuve d'usage, pas par anticipation
- [ ] `SecurityEngine` renforcé : sandboxing systématique (Docker) pour toute exécution de code généré
- [ ] Réévaluation du besoin d'event bus (seulement si un scénario concret de découplage se présente)

## v5.0 — Multi-agent réel

**Objectif** : plusieurs instances du kernel collaborent.

- [ ] Protocole de coordination inter-agents (A2A ou équivalent)
- [ ] Évaluation de l'Actor Model si la concurrence entre agents le justifie
- [ ] Questions de scalabilité multi-utilisateurs et CQRS réévaluées à ce stade seulement

---

## Ce qui déclenche une révision de cette roadmap

- Tout écart significatif entre un budget de latence mesuré et un budget prévu (voir cahier des charges §3).
- Toute décision de dépendre d'un composant externe majeur (framework d'agent complet, event bus, GPU cloud) — doit être justifiée par écrit avant d'être actée.
- Tout jalon qui prend plus de 2x le temps estimé — signal pour réduire le scope de la version en cours plutôt que d'insister.
