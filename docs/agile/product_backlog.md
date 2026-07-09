# Product Backlog — mlops-dataops-platform

**Product Owner** : Mouad
**Scrum Master** : Ghazli
**Équipe** : Ayoub, Mohamed, Maroua, Hajar, Lina, Mouad, Ghazli

Estimation en points (suite de Fibonacci : 1, 2, 3, 5, 8, 13).
Priorité : **Must** (bloquant), **Should** (important), **Could** (confort).

---

## Vision produit

Construire une plateforme MLOps/DataOps de bout en bout sur les données e-commerce Olist,
avec une architecture médaillon (Bronze/Silver/Gold), un pipeline ML industrialisé et une
CI/CD complète — livrée en 3 sprints, du plus bas niveau (ingestion brute) au plus haut
niveau (modèle servi en production).

---

## Epic 1 — Ingestion & Bronze (Sprint 1)

| ID | User Story | Assigné | Priorité | Points |
|---|---|---|---|---|
| US-01 | En tant que **Data Engineer ingestion**, je veux des sources dlt typées par format (CSV, JSON, API taux de change) afin de standardiser l'ingestion quelle que soit l'origine des données. | Ayoub | Must | 5 |
| US-02 | En tant que **Data Engineer ingestion**, je veux un pipeline dlt dédié par entité Olist (orders, customers, products, reviews, payments, sellers, geolocation, exchange_rates) afin d'isoler les échecs et de pouvoir relancer une entité sans impacter les autres. | Ayoub | Must | 8 |
| US-03 | En tant que **Data Engineer ingestion**, je veux un script `run_all_bronze` qui orchestre l'ensemble des pipelines Bronze en une seule commande afin de simplifier l'exécution manuelle et la CI. | Ayoub | Must | 3 |
| US-04 | En tant que **Data Engineer ingestion**, je veux un script de vérification (`verify_bronze`) qui contrôle que chaque table Bronze contient des lignes après ingestion afin de détecter immédiatement une source vide ou cassée. | Ayoub | Should | 3 |
| US-05 | En tant que **Data Engineer ingestion**, je veux que chaque table Bronze porte des colonnes de métadonnées (`_loaded_at`, `_source_file`, `_batch_id`) afin de garantir la traçabilité et la politique append-only. | Ayoub | Must | 5 |
| US-06 | En tant que **Data Analyst / Orchestration**, je veux des assets Dagster `bronze_*` correspondant à chaque pipeline dlt afin que l'ingestion soit visible et matérialisable depuis l'UI Dagster. | Lina | Must | 5 |
| US-07 | En tant que **Product Owner**, je veux un backlog priorisé et une vision produit documentée afin que l'équipe partage un référentiel commun avant le premier sprint. | Mouad | Must | 3 |
| US-08 | En tant que **Scrum Master / DevOps**, je veux un job CI `lint` (ruff) exécuté sur `dlt_pipelines/`, `ml/`, `api/` afin de garantir un niveau de qualité de code minimal dès le premier commit. | Ghazli | Should | 3 |

## Epic 2 — Transformation & Qualité (Sprint 2)

| ID | User Story | Assigné | Priorité | Points |
|---|---|---|---|---|
| US-09 | En tant que **Data Engineer transformation**, je veux des modèles dbt `bronze_*` (vues) exposant les tables dlt afin de découpler le schéma physique du modèle logique utilisé en aval. | Mohamed | Must | 3 |
| US-10 | En tant que **Data Engineer transformation**, je veux des modèles dbt Silver (`silver_orders`, `silver_customers`, `silver_products`, `silver_reviews`, `silver_payments`, `silver_sellers`, `silver_order_items`) avec cast de types, déduplication et normalisation afin de fournir une couche de données fiable et exploitable. | Mohamed | Must | 8 |
| US-11 | En tant que **Data Engineer transformation**, je veux des macros dbt réutilisables (`generate_surrogate_key`, `safe_cast_date`) afin d'éviter la duplication de logique SQL entre modèles. | Mohamed | Should | 3 |
| US-12 | En tant que **Data Engineer transformation**, je veux des modèles Gold (`gold_orders_summary`, `gold_customer_rfm`, `gold_product_performance`, `gold_seller_ranking`, `gold_reviews_features`) afin d'exposer des marts métier et un feature set prêt pour le ML. | Mohamed | Must | 8 |
| US-13 | En tant que **Data Engineer transformation**, je veux générer et publier le lineage dbt (`dbt docs generate` / `dbt docs serve`) afin que l'équipe visualise les dépendances Bronze→Silver→Gold. | Mohamed | Should | 3 |
| US-14 | En tant que **Data Engineer qualité**, je veux un data contract formalisé (schema.yml par couche avec tests `not_null`, `unique`, `accepted_values`, `relationships`, `dbt_expectations`) afin de garantir que les données respectent des règles métier explicites avant consommation. | Maroua | Must | 8 |
| US-15 | En tant que **Data Engineer qualité**, je veux des tests SQL custom (`assert_no_orphan_orders`, `assert_positive_revenue`, `assert_score_range`) afin de couvrir des règles de cohérence métier non exprimables par des tests génériques dbt. | Maroua | Must | 5 |
| US-16 | En tant que **Data Engineer qualité**, je veux un dictionnaire de données (`docs/data_dictionary.md`) documentant chaque table et colonne des couches Silver/Gold afin de faciliter l'onboarding et la maintenance. | Maroua | Should | 5 |
| US-17 | En tant que **Data Analyst / Orchestration**, je veux des assets Dagster `silver_*` et `gold_*` déclenchés après la matérialisation Bronze afin que l'orchestration reflète fidèlement les dépendances du pipeline médaillon. | Lina | Must | 5 |
| US-18 | En tant que **Data Analyst**, je veux explorer les tables Gold (RFM, performance produit, ranking vendeurs) afin de produire des premières analyses métier exploitables par le business. | Lina | Could | 5 |
| US-19 | En tant que **Scrum Master / DevOps**, je veux un job CI `test-dbt` qui ingère les fixtures puis exécute `dbt build` afin de valider automatiquement Silver et Gold à chaque push. | Ghazli | Must | 5 |

## Epic 3 — ML & Industrialisation (Sprint 3)

| ID | User Story | Assigné | Priorité | Points |
|---|---|---|---|---|
| US-20 | En tant que **Product Owner / ML Engineer**, je veux définir le problème ML (classification binaire satisfaction, target `satisfied = review_score >= 4`) et les features associées afin de cadrer le périmètre du modèle avant l'implémentation. | Mouad | Must | 3 |
| US-21 | En tant que **ML Engineer**, je veux un module `features.py` qui construit les features numériques et TF-IDF à partir de `gold_reviews_features` afin de séparer la préparation des données de l'entraînement. | Mouad | Must | 5 |
| US-22 | En tant que **ML Engineer**, je veux un script `train.py` qui entraîne une régression logistique et logue params/métriques/artefacts dans MLflow afin de tracer chaque expérimentation et pouvoir comparer les runs. | Mouad | Must | 8 |
| US-23 | En tant que **ML Engineer**, je veux un script `evaluate.py` calculant accuracy/F1/AUC afin d'objectiver la qualité du modèle avant promotion en registry. | Mouad | Must | 5 |
| US-24 | En tant que **ML Engineer**, je veux enregistrer le modèle validé dans le MLflow Model Registry (`SentimentClassifier`, stage `Production`) afin que l'API serve toujours la version validée la plus récente. | Mouad | Must | 3 |
| US-25 | En tant que **ML Engineer déploiement**, je veux une API FastAPI exposant `/predict` et `/health` avec chargement du modèle depuis MLflow au démarrage (lifespan) afin de servir les prédictions de façon fiable et observable. | Hajar | Must | 8 |
| US-26 | En tant que **ML Engineer déploiement**, je veux un endpoint `/reload` afin de recharger le modèle sans redémarrer le conteneur si une nouvelle version est promue en Production. | Hajar | Should | 3 |
| US-27 | En tant que **ML Engineer déploiement**, je veux un logger d'audit sur `/predict` (input/output/timestamp) afin de poser les bases du monitoring de dérive du modèle en production. | Hajar | Should | 5 |
| US-28 | En tant que **ML Engineer déploiement**, je veux des Dockerfiles dédiés (FastAPI, Dagster, MLflow) et un `docker-compose.yml` afin de livrer un stack complet, isolé et reproductible. | Hajar | Must | 8 |
| US-29 | En tant que **Data Analyst / Orchestration**, je veux un schedule Dagster quotidien (`daily_schedule`, 02:00 UTC) enchaînant Bronze→Silver→Gold→ml_training→api_model_check afin d'automatiser le pipeline complet sans intervention manuelle. | Lina | Must | 5 |
| US-30 | En tant que **Scrum Master / DevOps**, je veux des jobs CI `test-api`, `build-docker` et `smoke-test-api` afin de valider automatiquement les tests API, le build des images et la disponibilité du endpoint `/health` en conditions quasi-réelles. | Ghazli | Must | 8 |
| US-31 | En tant que **Scrum Master / DevOps**, je veux un runbook (`docs/runbook.md`) documentant le démarrage local, Docker, les commandes dbt/MLflow et la réinitialisation du projet afin que toute l'équipe puisse opérer la plateforme de façon autonome. | Ghazli | Should | 5 |
| US-32 | En tant que **Scrum Master**, je veux documenter les 3 sprints (objectifs, reviews, rétrospectives) dans `docs/agile/` afin de conserver une trace du déroulé du projet pour l'évaluation et les futurs contributeurs. | Ghazli | Must | 5 |

---

## Backlog non retenu (hors périmètre v1)

- SCD Type 2 sur la couche Silver/Gold (choix assumé, cf. `docs/architecture.md`).
- Monitoring de dérive de données/modèle avec alerting automatisé (le logging d'audit US-27 pose seulement les bases).
- Dashboard BI (Grafana/Power BI) connecté à la couche Gold — mentionné en architecture mais non implémenté dans ce dépôt.
