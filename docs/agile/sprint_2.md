# Sprint 2 — Transformation & Qualité

**Durée** : 1 semaine
**Objectif du sprint** : Construire les couches Silver et Gold avec dbt (nettoyage, déduplication, agrégats métier), formaliser un data contract testé automatiquement, documenter le dictionnaire de données et étendre l'orchestration Dagster et la CI en conséquence.

## User stories engagées

| ID | User Story | Assigné | Points |
|---|---|---|---|
| US-09 | Modèles dbt `bronze_*` (vues) | Mohamed | 3 |
| US-10 | Modèles dbt Silver (nettoyage, dédup, cast) | Mohamed | 8 |
| US-11 | Macros dbt réutilisables (`generate_surrogate_key`, `safe_cast_date`) | Mohamed | 3 |
| US-12 | Modèles Gold (marts + feature set ML) | Mohamed | 8 |
| US-13 | Lineage dbt (`dbt docs generate`/`serve`) | Mohamed | 3 |
| US-14 | Data contract (`schema.yml` par couche, tests génériques) | Maroua | 8 |
| US-15 | Tests SQL custom (orphelins, revenus positifs, score valide) | Maroua | 5 |
| US-16 | Dictionnaire de données (`docs/data_dictionary.md`) | Maroua | 5 |
| US-17 | Assets Dagster `silver_*` / `gold_*` | Lina | 5 |
| US-18 | Premières analyses métier sur les tables Gold | Lina | 5 |
| US-19 | Job CI `test-dbt` (fixtures → dbt build) | Ghazli | 5 |

**Total engagé** : 58 points

---

## Sprint Review

### Livré
- `dbt_project/models/bronze/*.sql` + `schema.yml` : vues exposant les tables dlt sans transformation.
- `dbt_project/models/silver/*.sql` : `silver_orders`, `silver_customers`, `silver_products`, `silver_reviews`, `silver_payments`, `silver_sellers`, `silver_order_items` — cast de types, déduplication sur clés naturelles, normalisation des statuts/valeurs catégorielles.
- `dbt_project/macros/generate_surrogate_key.sql` et `safe_cast_date.sql` — réutilisées dans plusieurs modèles Silver/Gold.
- `dbt_project/models/gold/*.sql` : `gold_orders_summary`, `gold_customer_rfm`, `gold_product_performance`, `gold_seller_ranking`, `gold_reviews_features` (ce dernier = feature set ML consommé au sprint 3).
- Lineage dbt généré et exploré via `dbt docs generate && dbt docs serve --port 8080`.
- `dbt_project/models/silver/schema.yml` et `dbt_project/models/gold/schema.yml` : data contract avec tests `not_null`, `unique`, `accepted_values`, `dbt_expectations.expect_column_values_to_be_between` sur les colonnes critiques (ex. `review_score` entre 1 et 5, `price` strictement positif).
- `dbt_project/tests/assert_no_orphan_orders.sql`, `assert_positive_revenue.sql`, `assert_score_range.sql` — règles métier custom non couvertes par les tests génériques.
- `dagster_project/assets/silver_assets.py` et `gold_assets.py` : assets dépendants des assets Bronze, exécutés dans l'ordre du DAG médaillon.
- `.github/workflows/ci.yml` — job `test-dbt` : ingestion des fixtures, vérification des row counts Bronze, `dbt deps`, `dbt build --target dev`.

### Non livré / reporté
- `docs/data_dictionary.md` a été rédigé mais reste à enrichir au fil des sprints suivants (colonnes ML ajoutées au sprint 3 à documenter a posteriori).
- Les analyses métier de Lina (US-18) restent exploratoires — pas de dashboard formalisé (hors périmètre v1, cf. backlog).

### Démo
- `dbt build --profiles-dir . --target dev` exécuté sur les fixtures CI → Silver et Gold matérialisés, tous les tests dbt passent (generic + custom).
- `dbt docs serve` → navigation dans le graphe de lineage Bronze→Silver→Gold.

---

## Sprint Retrospective

### Ce qui a bien marché
- Le data contract formalisé en `schema.yml` a permis de détecter des valeurs de `payment_type` non prévues avant qu'elles n'atteignent la couche Gold.
- Les macros réutilisables ont réduit la duplication SQL entre les 7 modèles Silver.
- Le découpage clair Bronze (vues) / Silver (nettoyage) / Gold (agrégats) a rendu le lineage dbt lisible dès la première génération.

### Ce qui peut être amélioré
- L'étape `dbt deps` avait été oubliée dans le job CI `test-dbt` au démarrage du sprint, faisant échouer le build sur les packages externes (`dbt-utils`, `dbt-expectations`) — corrigé en cours de sprint.
- Les versions `dlt`/`duckdb`/`dbt-core` ont dû être réalignées entre `requirements.txt` et la CI (incohérence héritée du sprint 1).
- Le dictionnaire de données a été rédigé en fin de sprint plutôt qu'au fil de l'eau, ce qui a demandé un rattrapage.

### Actions pour le sprint suivant
1. Vérifier systématiquement la présence de `dbt deps` (ou équivalent) avant tout job CI qui dépend de packages externes — check-list de revue de PR (portée par Ghazli).
2. Documenter le dictionnaire de données au fur et à mesure de la création de chaque modèle, plutôt qu'en fin de sprint.
3. Préparer dès le sprint 3 les tests d'intégration API en s'appuyant sur `gold_reviews_features`, déjà stable et testé.
