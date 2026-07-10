# Runbook — mlops-dataops-platform

## Démarrage local (sans Docker)

### Prérequis
```bash
python --version   # 3.11+
git --version
```

### Installation des dépendances par composant

```bash
# 1. dlt (ingestion Bronze)
pip install dlt[duckdb] python-dotenv

# 2. dbt (transformations Silver/Gold)
pip install dbt-duckdb dbt-utils

# 3. Dagster (orchestration)
pip install dagster dagster-webserver dagster-dbt

# 4. ML
pip install scikit-learn mlflow pandas duckdb

# 5. API
pip install fastapi uvicorn mlflow pydantic python-dotenv
```

### Exécution pipeline complet

```bash
# Depuis la racine du projet
cp .env.example .env

# Étape 1 : ingestion Bronze
python dlt_pipelines/pipelines/bronze_all.py

# Étape 2 : transformations Silver + Gold
cd dbt_project
dbt deps          # installe dbt-utils, dbt-expectations
dbt build         # run + test toutes les couches
dbt docs generate && dbt docs serve --port 8080

# Étape 3 : entraînement ML
cd ../ml/training
python train.py   # log dans MLflow local (./mlruns)

# Étape 4 : API
cd ../../api
uvicorn main:app --port 8100 --reload
```

## Démarrage Docker (stack complet)

```bash
cd docker
cp ../.env.example ../.env
docker compose up -d

# Vérifier les services
docker compose ps
curl http://localhost:3100/health   # Dagster
curl http://localhost:5100/health   # MLflow
curl http://localhost:8100/health   # FastAPI
```

### Lancer le pipeline depuis Dagster UI
1. Ouvrir http://localhost:3100
2. Aller dans **Assets** → sélectionner tout → **Materialize all**
3. Suivre la progression dans **Runs**

## Commandes dbt utiles

```bash
cd dbt_project

# Exécuter uniquement une couche
dbt run --select bronze
dbt run --select silver
dbt run --select gold

# Tests d'une couche
dbt test --select silver

# Voir le lineage
dbt docs generate
dbt docs serve
```

## Commandes MLflow

```bash
# Lister les expériences
mlflow experiments list

# Voir les runs
mlflow runs list --experiment-name olist-satisfaction

# Promouvoir un modèle en Production
mlflow models transition-stage \
  --name SentimentClassifier \
  --version 1 \
  --stage Production
```

## Tester l'API FastAPI

```bash
# Health check
curl http://localhost:8100/health

# Prédiction
curl -X POST http://localhost:8100/predict \
  -H "Content-Type: application/json" \
  -d '{
    "review_comment_message": "Produto chegou rápido e bem embalado",
    "delivery_delay_days": -2,
    "payment_type": "credit_card"
  }'
```

## Réinitialiser le projet

```bash
# Supprimer DuckDB (toutes les données)
rm warehouse/duckdb/olist.duckdb

# Supprimer les artefacts MLflow
rm -rf ml/mlflow/

# Supprimer les cibles dbt
rm -rf dbt_project/target/ dbt_project/logs/

# Relancer depuis zéro
python dlt_pipelines/pipelines/bronze_all.py
cd dbt_project && dbt build
```

## Variables d'environnement importantes

| Variable | Valeur par défaut | Description |
|---|---|---|
| `DATA_PATH` | `../data-engineering-platform/data/raw` | Chemin données sources |
| `DUCKDB_PATH` | `./warehouse/duckdb/olist.duckdb` | Fichier DuckDB |
| `MLFLOW_TRACKING_URI` | `http://localhost:5100` | Serveur MLflow |
| `MLFLOW_MODEL_NAME` | `SentimentClassifier` | Nom modèle registry |
| `DAGSTER_PORT` | `3100` | Port Dagster UI |
