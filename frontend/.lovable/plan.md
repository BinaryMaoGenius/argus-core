# Plan — UI debug COS (HTML autonome + snippet FastAPI)

## Livrable

Un seul fichier `cos_debug.html` (HTML/CSS/JS vanilla, zéro dépendance, zéro build) à poser dans ton projet Python et servir via `FileResponse("cos_debug.html")` sur `GET /`. Plus, en commentaire en tête du fichier, un snippet FastAPI de référence pour les routes `/chat/stream` (SSE) et `/chat/cancel` (POST).

Aucun code n'est exécuté côté Lovable — ce projet est TS/React, pas Python. Le fichier est autonome et se teste chez toi contre ton FastAPI local.

## Schéma d'événements SSE (contrat backend ↔ frontend)

Chaque message SSE = `event: <type>\ndata: <json>\n\n`. Types :

- `route` — décision de routage, émis avant le 1er token
  ```json
  { "path": "fast" | "slow", "model": "qwen2.5:0.5b", "reason": "semantic_cache" | "rule_match" | "classifier_0.5b" | "fallback", "detail": "texte libre optionnel" }
  ```
- `token` — un morceau de texte à concaténer
  ```json
  { "text": "..." }
  ```
- `done` — fin de génération, métriques finales
  ```json
  { "ttft_ms": 2830, "total_ms": 5120, "token_count": 42, "finish_reason": "stop" | "cancelled" | "error" }
  ```
- `error` — erreur backend
  ```json
  { "message": "..." }
  ```

Requête : `POST /chat/stream` avec `{ "message": "...", "request_id": "<uuid>", "history": [...] }`, réponse `text/event-stream`.
Annulation : `POST /chat/cancel` avec `{ "request_id": "<uuid>" }`.

Note : `EventSource` natif ne fait que GET. Deux options — je pars sur **fetch + ReadableStream** pour garder POST + body JSON + `AbortController` propre (cancel côté client instantané, plus POST /cancel côté serveur pour couper Ollama). Simple, ~40 lignes de parseur SSE.

## Fichier `cos_debug.html`

Structure :

```text
┌─ header : titre "COS debug" + statut backend (ping /health) ─┐
├─ historique : liste de bulles user / assistant              │
│    chaque bulle assistant porte :                            │
│      • badge route  [FAST — 0.5B · semantic_cache]           │
│        couleurs distinctes fast (vert) / slow (orange)       │
│      • corps texte, mis à jour token par token               │
│      • ligne métriques : TTFT 2.83s · total 5.12s · 42 tok   │
├─ zone "en cours" (pendant attente 1er token) :               │
│    • compteur live en secondes (0.1s tick), gros chiffre     │
│    • label "attente premier token…" puis "streaming…"        │
│    • bouton Cancel                                           │
└─ footer : textarea + bouton Send (Enter = send, Shift+Enter = newline)
```

Comportement JS :

1. `send(text)` : push bulle user, crée bulle assistant vide + placeholder metrics, démarre `t0 = performance.now()`, ouvre `fetch('/chat/stream', {method:'POST', body, signal})`.
2. Compteur d'attente : `setInterval` 100ms qui affiche `((now - t0)/1000).toFixed(1) + 's'` tant que `ttft` non défini. Le plancher 2.5-3s est donc visible en gros.
3. Parseur SSE incrémental sur `response.body.getReader()` : buffer texte, split sur `\n\n`, extrait `event:` et `data:`, dispatch.
4. Sur `route` → remplit le badge (path, model, reason, detail).
5. Sur premier `token` → note `ttft = now - t0`, arrête le compteur d'attente, bascule sur "streaming…", append text.
6. Suivants `token` → append text (textContent += pour éviter re-render coûteux ; scroll auto en bas).
7. Sur `done` → affiche ligne métriques finale à partir des valeurs backend (source de vérité) ; fallback sur mesures client si absentes.
8. Sur `error` ou `AbortError` → badge devient rouge, affiche message, garde ce qui a été streamé.
9. Cancel : `controller.abort()` côté client + `fetch('/chat/cancel', {..., request_id})` en fire-and-forget pour couper Ollama côté serveur.

Style :

- CSS dans `<style>`, ~100 lignes, système monospace (`ui-monospace, SFMono-Regular, Menlo`).
- Thème sobre : fond `#0e0e10`, texte `#e5e5e5`, bulles `#1a1a1d`, accent fast `#4ade80`, accent slow `#fb923c`, erreur `#f87171`.
- Badge = pill avec bordure 1px de la couleur du path, texte en `text-transform: uppercase; letter-spacing: .05em; font-size: 11px`.
- Métriques en `font-size: 12px; opacity: .7`, alignées à droite sous la bulle.
- Compteur d'attente : `font-size: 48px; font-variant-numeric: tabular-nums;` pour ne pas sauter visuellement à chaque tick.
- Zéro animation gratuite. Pas de spinner rotatif — juste le compteur numérique qui matérialise le plancher.

## Snippet FastAPI de référence (en commentaire dans le HTML)

Squelette non-exhaustif à adapter à ton routeur :

```python
# from fastapi import FastAPI, Request
# from fastapi.responses import StreamingResponse, FileResponse
# import json, asyncio
#
# app = FastAPI()
# CANCEL = set()  # request_ids annulés (remplace par un vrai registry)
#
# @app.get("/")
# def index(): return FileResponse("cos_debug.html")
#
# @app.post("/chat/stream")
# async def chat_stream(req: Request):
#     body = await req.json()
#     rid = body["request_id"]
#
#     async def gen():
#         decision = router.decide(body["message"])  # ton routeur
#         yield f"event: route\ndata: {json.dumps({'path': decision.path, 'model': decision.model, 'reason': decision.reason, 'detail': decision.detail})}\n\n"
#
#         t0 = time.perf_counter(); ttft = None; n = 0
#         async for tok in ollama_stream(decision.model, body["message"]):
#             if rid in CANCEL: break
#             if ttft is None: ttft = (time.perf_counter() - t0) * 1000
#             n += 1
#             yield f"event: token\ndata: {json.dumps({'text': tok})}\n\n"
#
#         total = (time.perf_counter() - t0) * 1000
#         yield f"event: done\ndata: {json.dumps({'ttft_ms': ttft, 'total_ms': total, 'token_count': n, 'finish_reason': 'cancelled' if rid in CANCEL else 'stop'})}\n\n"
#         CANCEL.discard(rid)
#
#     return StreamingResponse(gen(), media_type="text/event-stream",
#                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
#
# @app.post("/chat/cancel")
# async def cancel(req: Request):
#     CANCEL.add((await req.json())["request_id"])
#     return {"ok": True}
```

## Hors scope

- Multi-conversations / persistance historique (recharge = reset).
- Markdown/code highlighting dans les réponses (texte brut, cohérent avec "outil de debug").
- Auth, CORS avancé (même origine, servi par FastAPI).
- Retry, reconnexion SSE automatique.

## Étapes de build

1. Créer `cos_debug.html` à la racine du projet Lovable (tu le récupères et le déposes dans ton repo Python — Lovable ne l'exécutera pas mais le fichier sera là, propre et versionné).
2. Une fois posé, tu le charges dans FastAPI via `FileResponse` et testes contre ton Ollama local.
