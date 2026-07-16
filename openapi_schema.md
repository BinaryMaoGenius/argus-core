# OpenAPI corrigé pour COS MVP

## Endpoints

### GET /ping
- Description: endpoint de santé
- Réponse: `200`
- Body:
  - `status`: `ok`

### POST /decide
- Description: introspection optionnelle du routage sans lancer la génération
- Requête:
  - Paramètre de formulaire ou query string: `prompt` (string)
- Réponse: `200`
  - `path`: `fast` | `slow`
  - `model`: string
  - `reason`: string

### POST /generate
- Description: génération synchrone (non streaming)
- Requête JSON:
  - `prompt`: string (requis)
  - `model`: string (optionnel, override du routage)
  - `num_predict`: integer (optionnel, défaut 80)
  - `keep_alive`: string (optionnel, défaut `10m`)
- Réponse JSON: contenu renvoyé par le provider de modèle

### POST /generate/stream
- Description: génération streamée avec routage interne
- Requête JSON:
  - `prompt`: string (requis)
  - `model`: string (optionnel)
  - `num_predict`: integer (optionnel, défaut 80)
  - `keep_alive`: string (optionnel, défaut `10m`)
- Réponse: `text/event-stream`
- Format du flux: chunks JSON séparés par des sauts de ligne

Payloads de stream:
1. Premier chunk `routing`:
```json
{
  "type": "routing",
  "path": "fast",
  "model": "qwen2.5:0.5b",
  "reason": "short prompt"
}
```

2. Chunks de génération:
```json
{
  "response": "token text",
  "done": false
}
```
(ou tout autre format défini par le provider)

3. Chunk final `metrics`:
```json
{
  "type": "metrics",
  "time_to_first_token_s": 0.123,
  "total_time_s": 1.234,
  "approx_tokens": 12
}
```

### POST /memory/write
- Description: ajoute un item en mémoire
- Requête JSON:
  - `text`: string (requis)
  - `layer`: string (`working` | `recall` | `archival`, défaut `working`)
- Réponse:
  - `ok`: true
  - `layer`: value

### GET /memory/recall
- Description: recherche dans toutes les couches mémoire
- Paramètres query:
  - `q`: string
  - `top_k`: integer (optionnel, défaut 5)
- Réponse:
  - `query`: string
  - `results`: liste d’objets `{ layer, score, item }`

### POST /memory/save
- Description: sauvegarde l’archival sur disque
- Requête JSON:
  - `path`: string (requis)
- Réponse:
  - `saved`: true
  - `path`: string

### POST /memory/load
- Description: recharge l’archival depuis le disque
- Requête JSON:
  - `path`: string (requis)
- Réponse:
  - `loaded`: true
  - `path`: string
