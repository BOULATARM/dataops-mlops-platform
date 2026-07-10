# Sprint 1 — Ingestion & Bronze

**Durée** : 1 semaine
**Objectif du sprint** : Mettre en place la couche Bronze du pipeline médaillon : ingestion automatisée des données sources Olist (CSV/JSON/API) via dlt vers DuckDB, avec métadonnées de traçabilité, et une orchestration Dagster capable de matérialiser ces assets.

## User stories engagées

| ID | User Story | Assigné | Points |
|---|---|---|---|
| US-01 | Sources dlt typées par format (CSV, JSON, API taux de change) | Ayoub | 5 |
| US-02 | Pipeline dlt dédié par entité Olist | Ayoub | 8 |
| US-03 | Script `run_all_bronze` orchestrant l'ensemble des pipelines | Ayoub | 3 |
| US-04 | Script de vérification `verify_bronze` | Ayoub | 3 |
| US-05 | Colonnes de métadonnées d'ingestion (`_loaded_at`, `_source_file`, `_batch_id`) | Ayoub | 5 |
| US-06 | Assets Dagster `bronze_*` | Lina | 5 |
| US-07 | Backlog priorisé + vision produit | Mouad | 3 |
| US-08 | Job CI `lint` (ruff) | Ghazli | 3 |

**Total engagé** : 35 points

---

## Sprint Review

### Livré
- `dlt_pipelines/sources/` : `olist_csv.py`, `olist_json.py`, `exchange_rates.py` — une source dlt par type de format.
- `dlt_pipelines/pipelines/` : un pipeline par entité (`bronze_orders`, `bronze_customers`, `bronze_products`, `bronze_reviews`, `bronze_payments`, `bronze_sellers`, `bronze_geolocation`, `bronze_exchange`).
- `dlt_pipelines/pipelines/run_all_bronze.py` : orchestrateur qui exécute tous les pipelines Bronze en une commande (utilisé aussi bien en local qu'en CI).
- `dlt_pipelines/pipelines/verify_bronze.py` : contrôle post-ingestion (nombre de lignes > 0 par table).
- Toutes les tables `bronze.raw_*` portent bien `_loaded_at`, `_source_file`, `_batch_id`.
- `dagster_project/assets/bronze_assets.py` : un asset Dagster par pipeline Bronze, regroupés sous le groupe `bronze`.
- `docs/agile/product_backlog.md` : backlog initial avec vision produit.
- `.github/workflows/ci.yml` — job `lint` : `ruff check dlt_pipelines/ ml/ api/ --select E,F,W,I --ignore E501`.

### Non livré / reporté
- Aucun élément du sprint n'a été reporté — toutes les US planifiées ont été closes.

### Démo
- Exécution de `python -m dlt_pipelines.pipelines.run_all_bronze` sur les fixtures CI → 8 tables Bronze peuplées, vérifiées par `verify_bronze.py`.
- Matérialisation des assets `bronze_*` depuis l'UI Dagster (http://localhost:3100).

---

## Sprint Retrospective

### Ce qui a bien marché
- Découper l'ingestion par entité (un pipeline dlt = une source Olist) a permis de paralléliser le travail sans conflit de merge.
- Les métadonnées d'ingestion (`_loaded_at`, `_source_file`, `_batch_id`) ont été pensées dès le départ, évitant un refactor de la couche Bronze plus tard.
- Le script `run_all_bronze` unique a simplifié l'intégration en CI (une seule commande à invoquer).

### Ce qui peut être amélioré
- Les versions de `dlt`/`duckdb`/`dbt-core` n'avaient pas été verrouillées dès le sprint 1, ce qui a causé des instabilités CI découvertes seulement au sprint suivant.
- Le job Dagster n'avait pas encore de schedule à ce stade — la matérialisation restait manuelle.
- Manque de tests unitaires sur les sources dlt (couverts indirectement seulement via la CI d'intégration).

### Actions pour le sprint suivant
1. Aligner explicitement les versions `dlt` / `duckdb` / `dbt-core` entre `requirements.txt` et la CI (action portée par Ghazli).
2. Démarrer la couche Silver dès l'ouverture du sprint 2 pour ne pas bloquer les Data Analysts sur la donnée brute.
3. Ajouter un contrôle de qualité plus riche que le simple `COUNT(*) > 0` (anticipé par les US de l'Epic Qualité, sprint 2).
