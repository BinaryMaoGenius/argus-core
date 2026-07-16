# Comprendre ARGUS Core (Cognitive Operating System)

Ce document a pour but de vous aider à comprendre **l'essence du projet**, son fonctionnement interne et la philosophie unique qui le différencie des intelligences artificielles classiques.

---

## 1. Qu'est-ce que ARGUS Core ?

ARGUS Core (aussi appelé **COS** pour *Cognitive Operating System*) n'est pas un simple Chatbot. C'est un véritable **système d'exploitation cognitif local**.

Alors que des outils comme ChatGPT ou Claude fonctionnent sur le Cloud avec des serveurs surpuissants, ARGUS Core est conçu pour :
- **Tourner à 100% en local** sur votre ordinateur (Privacy-first).
- **Fonctionner sur des processeurs standards (CPU)** sans exiger de carte graphique (GPU) onéreuse.
- **Agir de manière autonome** sur vos fichiers, vos scripts et votre système, tout en restant sous votre contrôle (via un module de sécurité).

## 2. La Philosophie "Low-Tech / High-IQ"

Pour compenser la limitation matérielle (l'absence de GPU), le projet refuse l'approche naïve qui consisterait à demander au modèle d'Intelligence Artificielle de tout faire. Le cœur du projet repose sur **l'optimisation extrême des cycles d'horloge** :

1. **Le Routage Déterministe :** Pourquoi allumer un réseau de neurones complexe de 7 milliards de paramètres (7B) juste pour dire "Bonjour" ou pour lire un fichier ? ARGUS intercepte les demandes avec du code Python classique (très rapide) et ne réveille le gros modèle d'IA que pour les requêtes nécessitant un véritable raisonnement complexe.
2. **Skeleton-of-Thought (Squelette de Pensée) :** Quand le modèle d'IA doit concevoir un plan, on lui interdit de "parler" avec des phrases humaines. Il est forcé (via une contrainte matérielle appelée GBNF) à générer un tableau de données pur (JSON). Cela supprime le temps de calcul inutile.
3. **Les Macro-Outils :** Au lieu de faire réfléchir l'IA à chaque micro-action (ex: ouvrir le fichier, lire la ligne, modifier la ligne, sauvegarder), le système lui fournit des "Macro-outils" (ex: *Chercher et Remplacer*). L'IA donne l'ordre global, et le code Python exécute la boucle ultra-rapidement.

## 3. L'Anatomie du Système (Comment ça marche ?)

ARGUS Core est découpé en plusieurs **Moteurs (Engines)** indépendants, qui se comportent comme les organes d'un corps humain :

* 🧠 **Router (Le Triage)** : Le premier filtre. Il lit votre demande et décide s'il peut la résoudre instantanément ou s'il doit faire appel à la "réflexion profonde" (le LLM).
* 🗄️ **Memory Kernel (La Mémoire)** : Comme un véritable OS, ARGUS a de la "RAM" (Working Memory) pour se souvenir de la conversation en cours, et un "Disque Dur" (Archival Memory) pour mémoriser les succès passés et apprendre sans avoir besoin d'être ré-entraîné.
* 📝 **Planning Engine (Le Stratège)** : Face à un problème complexe, c'est lui qui décompose la tâche en une liste ordonnée de sous-tâches.
* ⚡ **Execution Engine (L'Ouvrier)** : Il prend le plan, et exécute les tâches. Il est **asynchrone**, c'est-à-dire qu'il peut exécuter plusieurs tâches indépendantes en même temps (parallélisation) pour gagner du temps.
* 🛡️ **Security Engine (Le Gardien)** : Avant que l'Execution Engine ne modifie un fichier ou lance une commande, le Security Engine vérifie si l'action est dangereuse et vous demande systématiquement l'autorisation (mode "Dry-Run").
* 🔌 **Tool Engine (Les Mains)** : C'est la boîte à outils. Elle contient les plugins (lecture de fichiers, écriture, exécution de scripts) que l'IA peut utiliser pour modifier votre système.

## 4. Le Cycle de vie d'une requête complexe

Pour bien comprendre, voici ce qu'il se passe lorsque vous demandez à ARGUS : *"Analyse ce script Python et corrige les bugs"* :

1. **Réception :** Le `Router` voit les mots "Analyse", "script" et "corrige". Il sait que c'est une tâche complexe. Il réveille le modèle d'IA lourd (`Qwen 7B`).
2. **Rappel Mémoire :** Le système va chercher dans ses archives s'il a déjà corrigé un script similaire dans le passé pour s'en inspirer (Few-Shot Learning).
3. **Préparation (Prefix-Stable) :** Le système compile votre historique de conversation, fige la mémoire cache de votre processeur pour ne pas recalculer ce qu'il a déjà lu (optimisation extrême).
4. **Planification :** L'IA génère en une fraction de seconde un plan structuré (JSON) : `[1. Lire fichier, 2. Analyser l'erreur, 3. Utiliser le Macro-outil Remplacer]`.
5. **Exécution sous surveillance :** Le plan est lancé. Mais au moment de réécrire le fichier (étape 3), le système s'arrête net. Le `Security Engine` vous prévient : *"L'agent veut modifier le script, acceptez-vous ?"*. Vous validez, la modification s'opère.

## 5. Pourquoi ce projet est unique ?

Là où l'industrie cherche à construire des modèles d'IA toujours plus gigantesques dans le cloud, ARGUS fait le pari inverse : **Construire le chef d'orchestre parfait autour d'une IA modeste.** 

C'est un produit pensé pour les contextes où la vie privée, le mode hors-ligne et les contraintes matérielles priment. C'est le socle d'un assistant qui ne se contente pas de vous parler, mais qui **travaille sur votre machine**, avec vos fichiers, comme un véritable collaborateur numérique.
