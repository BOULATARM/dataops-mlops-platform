# mlops-dataops-platform

Plateforme MLOps/DataOps complète basée sur les données e-commerce **Olist**.  
Architecture **médaillon** (Bronze / Silver / Gold) + pipeline ML bout-en-bout.

> **Projet indépendant** — fonctionne en parallèle de `data-engineering-platform/`  
> (Airflow + MySQL star-schema). Les deux projets partagent les mêmes données sources  
> en lecture seule mais n'ont aucune dépendance entre eux.

---

## Architecture médaillon

```
Sources Olist (CSV / JSON / API)
          │
          ▼  dlt (ingestion automatisée)
     ┌─────────────────────────────────┐
     │  BRONZE  — DuckDB schema bronze │  raw append-only, métadonnées d'ingestion
     │  raw_orders / raw_customers /   │  _loaded_at · _source_file · _batch_id
     │  raw_products / raw_reviews …   │
     └──────────────┬──────────────────┘
                    │  dbt (silver models)
     ┌──────────────▼──────────────────┐
     │  SILVER  — DuckDB schema silver │  nettoyage · dédup · cast types
     │  orders / customers / products  │  tests not_null · unique · accepted_values
     │  reviews / payments / sellers … │
     └──────────────┬──────────────────┘
                    │  dbt (gold models)
     ┌──────────────▼──────────────────┐
     │  GOLD    — DuckDB schema gold   │  agrégats métier · dimensions · marts ML
     │  orders_summary / customer_rfm  │
     │  product_perf / reviews_features│
     └──────────────┬──────────────────┘
                    │
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
    Scikit-learn ML      BI / Grafana
    (satisfaction        (données Gold
     classifier)         exposées)
          │
          ▼  MLflow tracking + registry
    FastAPI /predict
```

### Couche Bronze — données brutes

| Table DuckDB | Source | Politique |
|---|---|---|
| `bronze.raw_orders` | `olist_orders_dataset.csv` | append-only |
| `bronze.raw_customers` | `olist_customers_dataset.csv` | append-only |
| `bronze.raw_products` | `olist_products_dataset.csv` | append-only |
| `bronze.raw_reviews` | `olist_order_reviews_dataset.csv` | append-only |
| `bronze.raw_payments` | `olist_order_payments_dataset.csv` | append-only |
| `bronze.raw_sellers` | `olist_sellers_dataset.csv` | append-only |
| `bronze.raw_geolocation` | `olist_geolocation_dataset.csv` | append-only |
| `bronze.raw_exchange_rates` | `exchange_rates_snapshot.json` | append-only |

Chaque table contient les colonnes de métadonnées : `_loaded_at`, `_source_file`, `_batch_id`.

### Couche Silver — données nettoyées

Transformations appliquées par dbt :
- Cast des types (timestamps, décimaux, entiers)
- Déduplication sur les clés naturelles
- Normalisation des valeurs catégorielles (statuts, états)
- Filtrage des lignes invalides (nulls sur clés obligatoires)
- Tests automatiques : `not_null`, `unique`, `accepted_values`, `relationships`

### Couche Gold — marts métier + features ML

| Table | Usage |
|---|---|
| `gold.orders_summary` | KPIs commandes par client/mois |
| `gold.customer_rfm` | Scoring Récence/Fréquence/Montant |
| `gold.product_performance` | Revenus et volumes par produit/catégorie |
| `gold.seller_ranking` | Performance et fiabilité vendeurs |
| `gold.reviews_features` | **Feature set ML** : target + features numériques/textuelles |

---

## Mapping cahier des charges

### Politique d'exécution Dagster

Le pipeline s'exécute **à la demande**, lors d'un changement des données ou du code.
Le corpus Olist est historique ; le rejouer chaque nuit consommerait les ressources
du serveur et répéterait l'ingestion Bronze sans bénéfice de fraîcheur.
`daily_pipeline_02h_utc` reste donc `DefaultScheduleStatus.STOPPED` volontairement.
Le mode continu n'est pas un objectif de cette livraison. Un état déjà enregistré
dans Dagster prime sur ce défaut : vérifier l'UI Schedules de l'instance existante
et arrêter le schedule s'il avait été activé. L'état serveur n'a pas été vérifié ici.

| Composant CDC | Implémentation | Rôle |
|---|---|---|
| **dlt** | `dlt_pipelines/` | Ingestion CSV/JSON/API → Bronze DuckDB |
| **DuckDB** | `warehouse/duckdb/olist.duckdb` | Moteur de stockage unique (3 schémas) |
| **dbt** | `dbt_project/` | Transformations Bronze→Silver→Gold, tests, lineage |
| **Dagster** | `dagster_project/` | Orchestration assets + scheduling quotidien |
| **Scikit-learn** | `ml/training/` | Modèle classification satisfaction avis clients |
| **MLflow** | `ml/mlflow/` + serveur Docker | Experiment tracking + model registry |
| **FastAPI** | `api/` | Endpoint `/predict` + `/health` |
| **Docker** | `docker/docker-compose.yml` | Stack complet isolé (ports 3100/5100/8100) |
| **GitHub Actions** | `.github/workflows/ci.yml` | CI : lint → dbt test → build → smoke test |

---

## Prérequis

### Déploiement automatique

Sur un push vers `main`, `deploy` attend les builds et le smoke test puis exécute
`ansible/playbook.yml` sur le commit exact. Le périmètre de l'infrastructure EC2
existante est **FastAPI uniquement** ; MLflow doit être accessible depuis son conteneur.
Dans l'environnement GitHub `production`, configurer les secrets `DEPLOY_SSH_KEY`,
`DEPLOY_KNOWN_HOSTS` (empreinte vérifiée du serveur), et les variables `DEPLOY_HOST`,
`DEPLOY_USER`, `MLFLOW_TRACKING_URI` (URL sans identifiants). L'artifact
`deployment-<commit>-<tentative>` conserve le résultat Ansible et l'état Compose.
Un `/health` avec `model_loaded=false` fait échouer le déploiement.
La livraison reste à prouver par un premier run réussi ; aucune exécution distante
n'est déduite de la seule présence de ce job.

- Python 3.11+
- Docker Desktop
- Git

---

## Démarrage rapide

### 1. Variables d'environnement

```bash
cp .env.example .env
# Éditer .env si besoin (DATA_PATH, ports)
```

### 2. Lancer le stack Docker

Preuve horodatée de l'état réel (depuis la racine) :
`python docker/capture_compose_state.py`. Le fichier `docs/evidence/compose-state.json`
contient la commande, la sortie et son code de retour ; une erreur Docker n'est
pas une preuve de conteneurs opérationnels. Archiver ce fichier après chaque déploiement.

```bash
cd docker
docker compose up -d
```

Services disponibles :
- **Dagster UI** → http://localhost:3100
- **MLflow UI** → http://localhost:5100
- **FastAPI docs** → http://localhost:8100/docs

### 3. Exécuter le pipeline manuellement (sans Docker)

```bash
# Ingestion Bronze
cd dlt_pipelines
pip install -r requirements.txt
python pipelines/bronze_all.py

# Transformations Silver + Gold
cd ../dbt_project
pip install dbt-duckdb
dbt deps
dbt build

# Entraînement ML
cd ..
pip install -r ml/requirements.txt
python -m ml.training.train_v2

# API locale
pip install -r api/requirements.txt
uvicorn api.main:app --port 8100
```

### 4. Lineage dbt

La [documentation dbt téléchargeable dans les runs CI](https://github.com/BOULATARM/dataops-mlops-platform/actions/workflows/ci.yml)
est publiée sous `dbt-docs-<commit>` après le build sur fixtures (rétention : 30 jours).
Télécharger et extraire l'artifact, puis exécuter `python -m http.server 8080`
dans ce dossier et ouvrir `http://localhost:8080`. Le catalogue décrit les fixtures CI,
pas les volumes de production.

```bash
cd dbt_project
dbt docs generate
dbt docs serve --port 8080
```

---

## Structure du projet

```
mlops-dataops-platform/
├── dlt_pipelines/          # Ingestion sources → Bronze (dlt)
│   ├── sources/            # @dlt.source par type de source
│   └── pipelines/          # @dlt.pipeline par entité
├── warehouse/duckdb/       # olist.duckdb (créé à l'exécution)
├── dbt_project/
│   ├── models/bronze/      # Vues sur les tables dlt
│   ├── models/silver/      # Nettoyage + tests
│   ├── models/gold/        # Marts métier + features ML
│   ├── tests/              # Tests SQL custom
│   └── macros/             # Helpers SQL réutilisables
├── dagster_project/
│   ├── assets/             # Assets Dagster (bronze/silver/gold/ml)
│   ├── jobs/               # Jobs = combinaison d'assets
│   └── schedules/          # Scheduling quotidien
├── ml/
│   ├── training/           # train_v2.py + features.py (train_legacy.py déprécié) + evaluate.py
│   └── mlflow/             # Artefacts MLflow (volume Docker)
├── api/                    # FastAPI /predict + /health
├── docker/                 # docker-compose.yml + Dockerfiles
├── .github/workflows/      # CI/CD GitHub Actions
└── docs/                   # Architecture + runbook
```

---

## Modèle ML — Satisfaction avis clients

**Problème** : classification binaire  
**Target** : `satisfied = 1` si `review_score >= 4`, sinon `0`  
**Features** :
- `review_comment_length` — longueur du commentaire (chars)
- `has_comment` — présence ou non d'un commentaire textuel
- `delivery_delay_days` — délai entre date estimée et date réelle
- `payment_type_encoded` — encodage catégoriel entier du type de paiement
- TF-IDF (500 termes maximum, n-grammes 1–2, min_df=5) sur `review_comment_message`

**Algorithme** : `LogisticRegression` (sklearn), baseline solide et interprétable  
**Tracking** : MLflow (params, métriques accuracy/F1/AUC, artefact modèle)  
**Registry** : modèle enregistré sous `SatisfactionClassifier` → stage `Production`

---

## Isolation par rapport à data-engineering-platform

| Aspect | data-engineering-platform | mlops-dataops-platform |
|---|---|---|
| Orchestration | Airflow | Dagster |
| Stockage | MySQL (star schema) | DuckDB (médaillon) |
| ETL | Talend | dlt + dbt |
| Ports | 8080/3306/27017/3000 | 3100/5100/8100 |
| Réseau Docker | `dep-network` | `mlops-network` |
| Données sources | Lues depuis `data/raw/` | Même fichiers, montés en lecture seule |


### Source de vérité de l'entraînement

Depuis la racine : `python -m ml.training.train_v2` (après `dbt build`).
Ce point d'entrée utilise le texte + les quatre numériques, TF-IDF et
`LogisticRegression(solver="liblinear", class_weight="balanced")`.
`train_legacy.py` conserve la baseline numérique historique et refuse une exécution directe.
Le code v2 a été reconstruit à partir des paramètres de l'audit : son identité exacte
avec le script serveur ayant produit v19 reste à vérifier. Aucun candidat n'est promu
automatiquement ni écrit par-dessus v19. L'API accepte le champ optionnel
`review_comment_message` ; les anciens clients restent acceptés avec un texte vide,
mais n'apportent pas le signal textuel utile au modèle v2.

### Qualité des clés et stabilité des volumes

Les tests SQL vérifient `(order_id, payment_sequential)` et `(order_id, order_item_id)`,
y compris leurs composantes nulles. Silver garde la dernière ingestion de chaque paire.
Avant chaque reconstruction, un pre-hook conserve le compte précédent dans
`main_silver._volume_baseline_<modèle>`. Le test échoue pour une variation absolue
supérieure à 20 % (`--vars '{volume_tolerance: 0.20}'`). Une base précédente vide
ne peut devenir non vide sans signalement. Au premier build, la référence NULL
indique une initialisation, pas une stabilité démontrée. `dbt test` ne modifie pas
la référence. Conserver DuckDB entre les runs et examiner tout échec avant une relance
(un nouveau build remplace la référence). En CI, deux builds sur les mêmes fixtures
vérifient le chemin avec référence ; ce n'est pas un historique de production.
