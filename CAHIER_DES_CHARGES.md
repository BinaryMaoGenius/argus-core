# Cahier des charges — Cognitive Operating System (COS)

**Auteur** : Emmanuel (BinaryMalianGenius / BMG)
**Statut** : v0.1 — document vivant, à réviser à chaque jalon de la roadmap
**Machine de référence** : Windows, 16-32 Go RAM, pas de GPU dédié, Ollama local

---

## 1. Objectif du projet

Construire un **Cognitive Operating System (COS)** : un noyau cognitif open source, local-first, modulaire et indépendant du modèle de langage, capable de transformer un objectif en plan, d'utiliser des outils, de vérifier ses hypothèses, de mémoriser ses expériences et de s'améliorer sans réentraînement du modèle.

**Ce que le projet n'est pas** : un agent framework de plus, ni une tentative de reconstruire en moins bien ce qui existe déjà (Letta/MemGPT, Zep/Graphiti, MCP). Le projet réutilise ces briques quand elles couvrent un besoin, et concentre l'effort d'ingénierie propre sur ce qui n'existe pas ailleurs : un système cognitif local-first optimisé pour du matériel contraint (CPU seul), avec un cas d'usage réel ancré dans le contexte malien (Wari Agent, traducteur Bambara, outils BMG).

## 2. Contraintes fondatrices (non négociables)

| Contrainte | Détail | Origine |
|---|---|---|
| **Local-first** | Aucune dépendance obligatoire à un service cloud pour fonctionner | Vision initiale du projet |
| **Indépendance au modèle** | Remplacer Qwen par Llama/Mistral/DeepSeek ne doit pas nécessiter de modifier le kernel | Vision initiale, validée par le design Model Adapter |
| **Pas de fine-tuning au démarrage** | Aucun GPU dédié disponible ; le fine-tuning local n'est pas réaliste (mur matériel, pas juste un choix) | Diagnostic hardware confirmé |
| **Solo dev** | Le scope de chaque version doit rester réalisable par une seule personne en parallèle d'études et de freelance | Réalité du porteur de projet |
| **Chemin critique in-process** | Fast path et slow path tournent dans un seul process Python, sans event bus, sans réseau, jusqu'à preuve du besoin contraire | Décision issue du débat architecture (voir §6) |

## 3. Contraintes matérielles mesurées (à respecter dans toute décision de design)

Mesures réalisées sur la machine cible avec `qwen2.5:0.5b` (routeur) et `qwen2.5-coder:7b` (exécution), via Ollama, `OLLAMA_MAX_LOADED_MODELS=2` :

| Métrique | Valeur mesurée | Implication |
|---|---|---|
| **Plancher de latence par appel** | ~2,5-3s (`time_to_first_token`), quasi indépendant de la taille du modèle | Aucun budget de latence sous ce seuil n'est atteignable ; c'est un coût fixe (overhead CPU/tokenisation), pas une variable d'architecture |
| **Débit de génération du 7B** | ~4,3-4,8 tokens/s, stable quel que soit le type de tâche | La longueur de sortie (`num_predict`) est le seul levier direct sur le temps total d'une réponse |
| **Coût de bascule entre modèles résidents** | Nul (mesuré) quand `OLLAMA_MAX_LOADED_MODELS=2` est actif | Le routeur peut basculer aussi souvent que nécessaire entre 0.5B et 7B sans pénalité de conception |
| **Effet du `keep_alive`** | ~8-10s de coût de rechargement si le modèle est déchargé (confirmé v1, non reproduit en v2 grâce à la résidence forcée) | `keep_alive` long + double résidence obligatoires en production locale |

**Budgets de latence dérivés (remplacent tout chiffre arbitraire posé en amont)** :
- **Fast path** : ~3-6s pour une réponse courte contrainte (`num_predict` ≈ 50-150)
- **Slow path** : plusieurs dizaines de secondes à quelques minutes pour une réponse complète (`num_predict` ≈ 300-1000+), latence *perçue* gérée par streaming, pas par réduction du temps total
- **Background path** : sans contrainte de latence, isolé en process séparé uniquement si un futur benchmark démontre une dégradation du chemin critique sans cette isolation

## 4. Architecture cible

### 4.1 Principe général
Kernel cognitif composé de services (Engines) découplés par des **contrats d'interface clairs** (schémas d'entrée/sortie explicites), communiquant par **appel de fonction async in-process** (pas d'event bus tant que le besoin n'est pas prouvé). Chaque Engine est testable isolément en mockant le Model Adapter.

### 4.2 Services du kernel (périmètre complet, implémentation progressive selon la roadmap)

| Engine | Rôle |
|---|---|
| Model Adapter | Seule couche qui parle au LLM ; abstrait Ollama derrière une interface `ModelProvider` |
| Router (Triage) | Décide fast / slow / background avant tout appel coûteux ; hybride règles → 0.5B → 7B |
| Memory Engine | Working / Recall / Archival (voir §5), interface unique `recall()` / `write()` |
| Planning Engine | Décompose un objectif en sous-tâches |
| Reasoning Engine | Raisonnement, analyse, choix entre options |
| Tool Engine | Registre + invocation d'outils, idéalement via MCP |
| Execution Engine | Orchestre l'exécution effective d'un plan |
| Verification Engine | Produit un "belief record" (connu / inféré / supposé / confiance / sources / non-vérifié) avant toute action à effet de bord |
| Reflection Engine | Post-mortem après exécution |
| Learning Engine | Bibliothèque de plans réussis + prompts versionnés (pas de modification de poids) |
| Knowledge Engine | RAG documentaire (pgvector) |
| Security Engine | Sandboxing, permissions ; s'interpose systématiquement avant toute action à effet de bord réel, indépendamment du path emprunté |
| API Gateway | FastAPI, point d'entrée unique |
| Scheduler | Jobs de fond (consolidation mémoire, préfetch) |

### 4.3 Cycle cognitif (version révisée, avec triage et boucles explicites)

```
Objectif reçu
  → [Router] trivial ? → Reasoning Engine direct (fast path) → réponse streamée
  → complexe ? → Comprendre + récupérer contexte mémoire (parallèle)
     → Décomposer
     → Boucle {Planifier → Vérifier (Verification Engine) → si confiance insuffisante,
       revenir à Planifier ou Comprendre} jusqu'à confiance suffisante ou budget épuisé
     → Exécuter (Tool Engine, sous supervision Security Engine)
     → Observer → échec ? → réviser ou escalader vers l'humain
     → Évaluer → Réflexion → Leçons → Learning Engine → MAJ mémoire
```

**Garde-fou non négociable** : toute action à effet de bord réel (écriture fichier, commande shell, appel réseau sortant) passe obligatoirement par le slow path et le Security Engine, peu importe ce que dit le triage sur la simplicité apparente de la requête.

## 5. Architecture mémoire

Trois couches (working / recall / archival), interface unique côté kernel : `recall(query, scope) -> context_bundle`. Le reste du système ignore où vit l'information (détail d'implémentation caché dans le Memory Engine).

- **Couche 1 — Working Memory** : contexte actif, strictement bornée en tokens (le plancher de latence mesuré rend chaque token de contexte coûteux en CPU).
- **Couche 2 — Recall Memory** : historique de conversation, hors contexte, interrogeable.
- **Couche 3 — Archival** : mémoire de projet, erreurs, succès, décisions, utilisateur, documentaire. Démarre en **vectoriel simple (pgvector)** ; un graphe temporel (type Graphiti) n'est envisagé qu'en v2.0+ si le besoin de traçabilité des faits dans le temps est prouvé par l'usage réel.

## 6. Décisions d'architecture actées (issues du débat documenté)

1. **Pas d'event bus avant v2.0.** Fast path et slow path in-process. Un event bus, une sérialisation réseau même locale, ajoutent un coût au chemin critique sans contrepartie mesurée à l'échelle mono-utilisateur.
2. **Background path isolable, mais conditionnellement.** Un worker séparé (`multiprocessing`) est justifié uniquement pour éviter la concurrence CPU entre une tâche de fond et l'inférence du chemin critique — pas comme principe de distribution.
3. **Routeur hybride, pas un seul modèle.** Règles/heuristiques (regex sur actions destructrices, cache sémantique, longueur de requête) en première passe, gratuites ; le 0.5B tranche seulement si les règles ne suffisent pas ; le 7B n'intervient que sur décision du triage.
4. **Sortie contrainte par path.** `num_predict` bas et fixe pour le triage (~20 tokens) ; borné pour le fast path (~100-150) ; plus large mais toujours plafonné pour le slow path (~300-1000).
5. **Streaming systématique.** La latence perçue prime sur la latence totale, vu le débit fixe du 7B.
6. **Stack mono-langage Python jusqu'à preuve du besoin contraire.** Pas de Rust pour le kernel — complexité disproportionnée pour un solo dev à ce stade.
7. **Pas de fine-tuning local.** Ingénierie de contexte uniquement (plans réussis, prompts versionnés) tant qu'aucun GPU n'est disponible.

## 7. Stack technique retenue

| Couche | Choix | Justification |
|---|---|---|
| Backend / kernel | Python + FastAPI (async) | Cohérent avec la stack existante (Django/DRF), async nécessaire pour l'I/O LLM |
| Base relationnelle | PostgreSQL | Déjà dans la stack de l'auteur |
| Mémoire vectorielle | pgvector | Évite un service supplémentaire tant que le volume ne le justifie pas |
| Outils | MCP en priorité, interface `ToolPlugin` custom en complément | Ne pas réinventer un protocole déjà standardisé |
| Modèle | Ollama (Qwen2.5:0.5b routeur + Qwen2.5-Coder:7b exécution) | Déjà en place et mesuré |
| Bus d'événements | Aucun avant v2.0 | Voir §6.1 |
| Observabilité | Logs JSON structurés (pas de stack Prometheus/Grafana avant besoin réel) | Cohérence avec la frugalité imposée par le hardware |
| Tests | pytest, tests de contrat par Engine (mock du Model Adapter) | Chaque Engine testable indépendamment du LLM |
| Déploiement | Docker Compose local ; Coolify en option future | Cohérent avec l'exploration déjà en cours côté self-hosting |

## 8. Ce que le projet ne fait pas (périmètre exclu explicitement)

- Pas de fine-tuning / modification de poids tant qu'aucun GPU n'est disponible.
- Pas de multi-agent distribué avant v5.0.
- Pas de CQRS avant qu'un besoin réel de séparation lecture/écriture à charge élevée soit démontré.
- Pas d'UI avant que le kernel fonctionne en CLI.
- Pas de graphe de connaissances temporel avant que le besoin de traçabilité des faits soit prouvé par l'usage.

## 9. Critères de succès de la v0.1

- Un chat CLI qui garde le contexte d'une session (working memory uniquement).
- Router fonctionnel (règles + 0.5B) avec des temps de réponse fast path mesurés dans la fourchette 3-6s.
- Aucune régression du plancher de latence par rapport aux benchmarks de référence (§3).
- Tests de contrat passants sur le Model Adapter et le Router, indépendamment d'Ollama (mock).

## 10. Références et sources ayant influencé les décisions

- MemGPT / Letta — architecture mémoire tiered (core/recall/archival), UC Berkeley.
- Zep / Graphiti (arXiv 2501.13956) — graphe de connaissances temporel pour mémoire d'agent.
- Model Context Protocol (Anthropic) — standard d'interopérabilité outils/contexte.
- Reflexion — feedback textuel structuré pour l'amélioration sans mise à jour de poids.
- Comparatifs LangGraph / CrewAI / AutoGen 2026 — choix de ne pas adopter un framework complet, préférence pour un kernel custom léger inspiré de leurs patterns.
- Benchmarks internes réalisés sur la machine cible (`benchmark_ollama.py`, `benchmark_ollama_v2.py`) — seule source de vérité pour les budgets de latence.
