# Architecture — mlops-dataops-platform

## Flux de données bout-en-bout

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          SOURCES (lecture seule)                        │
│  CSV: orders · customers · products · reviews · payments · sellers      │
│  JSON: products_sample · exchange_rates_snapshot                        │
│  Path: $DATA_PATH (configurable via .env)                               │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │  dlt pipeline
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    BRONZE  (DuckDB schema: bronze)                      │
│  Politique : append-only, aucune transformation                         │
│  Colonnes systèmes : _loaded_at · _source_file · _batch_id             │
│  Tables : raw_orders · raw_customers · raw_products · raw_reviews       │
│           raw_payments · raw_sellers · raw_geolocation · raw_exchange   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │  dbt models (silver layer)
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    SILVER  (DuckDB schema: silver)                      │
│  Politique : table incrémentale ou full-refresh selon la source         │
│  Opérations : cast types · dédup · filtre nulls · normalisation         │
│  Tests dbt : not_null · unique · accepted_values · relationships        │
│  Tables : orders · customers · products · reviews · payments · sellers  │
│           order_items                                                   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │  dbt models (gold layer)
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    GOLD  (DuckDB schema: gold)                          │
│  Politique : full-refresh (agrégats recalculés quotidiennement)         │
│  Tables :                                                               │
│    orders_summary      — KPIs commandes (CA, nb, panier moyen)          │
│    customer_rfm        — Scoring RFM par client                         │
│    product_performance — Revenus et volumes par produit/catégorie       │
│    seller_ranking      — Performance vendeurs (délai, note, CA)         │
│    reviews_features    — Feature set ML (target + features)             │
└────────────┬─────────────────────────────────┬──────────────────────────┘
             │                                 │
             ▼  ml/training/train.py           ▼  BI / reporting
    ┌──────────────────┐              ┌─────────────────────┐
    │  Scikit-learn    │              │  Grafana / Power BI │
    │  LogisticReg.    │              │  (données Gold via  │
    │  TF-IDF + feats  │              │   DuckDB connector) │
    └────────┬─────────┘              └─────────────────────┘
             │  mlflow.log_model
             ▼
    ┌──────────────────┐
    │  MLflow Registry │
    │  SentimentClass. │
    │  stage=Production│
    └────────┬─────────┘
             │  mlflow.pyfunc.load_model
             ▼
    ┌──────────────────┐
    │  FastAPI         │
    │  POST /predict   │
    │  GET  /health    │
    └──────────────────┘
```

## Orchestration Dagster — Asset graph

```
bronze_orders ──────┐
bronze_customers ───┤
bronze_products ────┤──▶ silver_layer ──▶ gold_layer ──▶ ml_training ──▶ api_model_check
bronze_reviews ─────┤
bronze_payments ────┤
bronze_sellers ─────┘
```

Chaque nœud est un `@asset` Dagster. Le `full_pipeline_job` les relie tous.  
Schedule : quotidien à 02:00 UTC.

## Décisions d'architecture

### Pourquoi DuckDB ?
- Moteur analytique embarqué, zéro infrastructure serveur
- Lecture native des CSV/Parquet — idéal pour dlt
- Compatible dbt-duckdb, excellent pour le dev local et les tests CI

### Pourquoi dlt pour l'ingestion ?
- Gestion automatique du schéma (type inference)
- Métadonnées d'ingestion out-of-the-box (`_loaded_at`, `_dlt_load_id`)
- Connecteurs natifs pour fichiers locaux et APIs REST

### Pourquoi Dagster plutôt qu'Airflow ?
- Airflow est déjà utilisé dans `data-engineering-platform`
- Dagster : paradigme asset-first (lignage visible), meilleur support Python natif
- Pas de duplication d'orchestrateur entre les deux projets

### SCD et historisation
La couche Bronze est **append-only** : chaque ingestion ajoute des lignes sans écraser.  
La couche Silver **déduplique** en gardant la dernière version par clé naturelle.  
La couche Gold est **full-refresh** quotidien (agrégats toujours recalculés).  
Il n'y a pas de SCD Type 2 dans ce projet — c'est la différence principale avec  
le star-schema de `data-engineering-platform` qui implémente SCD2 sur dim_customer.
