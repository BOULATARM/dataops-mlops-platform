# Sprint 3 — ML & Industrialisation

**Durée** : 1 semaine
**Objectif du sprint** : Entraîner et tracer le modèle de classification de satisfaction client, l'enregistrer dans le MLflow Model Registry, le servir via une API FastAPI conteneurisée, automatiser l'ensemble via Dagster et sécuriser la livraison avec une CI/CD complète (build, tests, smoke test).

## User stories engagées

| ID | User Story | Assigné | Points |
|---|---|---|---|
| US-20 | Cadrage du problème ML (target, features) | Mouad | 3 |
| US-21 | Module `features.py` (numériques + TF-IDF) | Mouad | 5 |
| US-22 | Script `train.py` (entraînement + tracking MLflow) | Mouad | 8 |
| US-23 | Script `evaluate.py` (accuracy/F1/AUC) | Mouad | 5 |
| US-24 | Enregistrement modèle en Registry (stage Production) | Mouad | 3 |
| US-25 | API FastAPI `/predict` + `/health` | Hajar | 8 |
| US-26 | Endpoint `/reload` | Hajar | 3 |
| US-27 | Logging d'audit sur `/predict` | Hajar | 5 |
| US-28 | Dockerfiles + `docker-compose.yml` | Hajar | 8 |
| US-29 | Schedule Dagster quotidien (pipeline complet) | Lina | 5 |
| US-30 | Jobs CI `test-api`, `build-docker`, `smoke-test-api` | Ghazli | 8 |
| US-31 | Runbook (`docs/runbook.md`) | Ghazli | 5 |
| US-32 | Documentation agile des 3 sprints | Ghazli | 5 |

**Total engagé** : 71 points

---

## Sprint Review

### Livré
- `ml/training/features.py` : construction des features numériques (`delivery_delay_days`, `review_comment_length`, `has_comment`, `payment_type_encoded`) et TF-IDF (50 features) à partir de `gold.gold_reviews_features`.
- `ml/training/train.py` : entraînement `LogisticRegression`, tracking MLflow (params, métriques, artefact modèle) sur l'expérience `olist-satisfaction-v2`.
- `ml/training/evaluate.py` : calcul accuracy / F1 / AUC pour valider le modèle avant promotion.
- Modèle enregistré dans le MLflow Model Registry sous `SentimentClassifier` / `SatisfactionClassifier` (nom configurable via `MLFLOW_MODEL_NAME`), stage `Production`.
- `api/main.py` : FastAPI avec lifespan qui charge le modèle au démarrage, `GET /health` (toujours 200, `model_loaded` reflète l'état réel), `POST /predict` (503 si modèle non chargé), `POST /reload`.
- Logger d'audit `predict_audit` : timestamp, features en entrée, prédiction et probabilité en sortie sur chaque appel `/predict`.
- `docker/Dockerfile.fastapi`, `docker/Dockerfile.dagster`, `docker/Dockerfile.mlflow`, `docker/docker-compose.yml` : stack complet (ports 3100/5100/8100, réseau `mlops-network`).
- `dagster_project/schedules/daily_schedule.py` : exécution quotidienne à 02:00 UTC de `full_pipeline_job` (Bronze→Silver→Gold, dépendances déclarées par asset).
- `.github/workflows/ci.yml` — jobs `test-api` (pytest + MockModel), `build-docker` (build des 2 images sans push), `smoke-test-api` (lancement du conteneur, poll `/health`, vérification `status=ok`, appel `/predict` sans modèle → 503 attendu).
- `docs/runbook.md` : démarrage local et Docker, commandes dbt/MLflow utiles, procédure de réinitialisation, variables d'environnement.

### Non livré / reporté
- Le job Dagster `ml_training` et `api_model_check` mentionnés dans l'architecture cible ne sont pas encore des assets Dagster autonomes — l'entraînement reste déclenché manuellement (`python train.py`) ; leur intégration au DAG Dagster est proposée en backlog de suivi.
- Le monitoring de dérive du modèle se limite au logging d'audit (US-27) ; pas d'alerting automatisé (hors périmètre v1).

### Démo
- `python train.py` → run MLflow visible sur http://localhost:5100, modèle promu en `Production`.
- `docker compose up -d` → 3 services démarrés ; `curl http://localhost:8100/health` → `{"status":"ok","model_loaded":true,...}`.
- `curl -X POST http://localhost:8100/predict ...` → réponse avec `satisfied` et `probability`.
- Pipeline CI complet vert : lint → test-dbt → test-api → build-docker → smoke-test-api.

---

## Sprint Retrospective

### Ce qui a bien marché
- Le découplage `ModelLoader` / route FastAPI a permis de tester `/health` et `/predict` sans modèle réel (`MockModel` en CI), simplifiant les tests API.
- Le smoke test Docker (`smoke-test-api`) a détecté tôt un problème réel de démarrage avant toute mise en Docker réelle par un utilisateur.
- Séparer `train.py` / `evaluate.py` / `features.py` a permis de itérer sur le modèle sans dupliquer la logique de préparation des données.

### Ce qui peut être amélioré
- Les retries HTTP par défaut de MLflow bloquaient le démarrage du conteneur FastAPI en CI (le `lifespan` restait bloqué en attente de connexion MLflow) — diagnostiqué tardivement dans le sprint via les logs du smoke test.
- Le pipeline Dagster ne couvre pas encore l'étape ML de bout en bout (entraînement + vérification API) malgré ce qui est documenté dans l'architecture cible.
- Plusieurs correctifs CI (versions de dépendances, étape `dbt deps` manquante, retries MLflow) ont dû être faits dans l'urgence en fin de sprint plutôt qu'anticipés.

### Actions pour le prochain cycle
1. Ajouter `MLFLOW_HTTP_REQUEST_MAX_RETRIES=0` (ou équivalent) par défaut en environnement CI/smoke test pour éviter tout blocage du lifespan FastAPI (déjà appliqué en correctif, à documenter dans `docs/runbook.md`).
2. Créer les assets Dagster `ml_training` et `api_model_check` pour clore l'écart entre l'architecture documentée et l'implémentation réelle.
3. Mettre en place une revue de dépendances (dlt/duckdb/dbt-core/mlflow/scikit-learn) en début de sprint plutôt qu'en réaction à un échec CI.
