# Data Contract — mlops-dataops-platform

Ce document formalise le contrat de données entre les sources Olist et la couche
Bronze, et entre les couches Bronze → Silver → Gold. Il complète le dictionnaire
de données (`docs/data_dictionary.md`) en explicitant le schéma attendu, les
types, les contraintes et la politique d'évolution.

---

## 1. Portée du contrat

Le contrat couvre :
- Les 8 sources Olist ingérées par dlt (CSV/JSON) et l'API taux de change.
- Les garanties offertes par chaque couche du médaillon (Bronze append-only,
  Silver nettoyée/dédupliquée, Gold agrégée).
- Les règles de validation automatisées (tests dbt génériques + tests custom).

Il ne couvre pas le contrat d'API du endpoint `/predict` (voir `api/schemas.py`
et `docs/runbook.md`).

---

## 2. Schéma attendu des sources Olist

| Source | Format | Colonnes obligatoires | Type attendu |
|---|---|---|---|
| `olist_orders_dataset.csv` | CSV | `order_id`, `customer_id`, `order_status`, `order_purchase_timestamp` | string, string, string (enum), timestamp |
| `olist_customers_dataset.csv` | CSV | `customer_id`, `customer_unique_id` | string, string |
| `olist_order_items_dataset.csv` | CSV | `order_id`, `order_item_id`, `product_id`, `seller_id`, `price`, `freight_value` | string, int, string, string, decimal, decimal |
| `olist_products_dataset.csv` | CSV | `product_id` | string |
| `olist_order_reviews_dataset.csv` | CSV | `review_id`, `order_id`, `review_score`, `review_comment_message` | string, string, int (1-5), string nullable |
| `olist_order_payments_dataset.csv` | CSV | `order_id`, `payment_type`, `payment_value` | string, string (enum), decimal |
| `olist_sellers_dataset.csv` | CSV | `seller_id` | string |
| `olist_geolocation_dataset.csv` | CSV | `geolocation_zip_code_prefix`, `geolocation_lat`, `geolocation_lng` | string, float, float |
| `product_category_name_translation.csv` | CSV | `product_category_name`, `product_category_name_english` | string, string |
| `exchange_rates_snapshot.json` | JSON | `currency_code`, `rate`, `base_currency`, `fetched_at` | string, decimal, string, timestamp |
| `products_sample.json` | JSON | `product_id`, `product_name`, `category`, `unit_price`, `unit_cost` | string, string, string, decimal, decimal |

**Garantie dlt** : chaque ligne ingérée reçoit automatiquement `_loaded_at`
(timestamp UTC), `_source_file` (nom du fichier source) et `_batch_id`
(UUID de l'exécution), sans altération des colonnes métier.

---

## 3. Contraintes par couche

### Bronze (append-only)
- Aucune transformation, aucune contrainte de validité — les données brutes
  sont conservées telles quelles, y compris les lignes invalides.
- Seule garantie testée : présence d'au moins une ligne par table après
  ingestion (`verify_bronze.py`, job CI `test-dbt`).

### Silver (nettoyée)
- **Unicité** : clé naturelle unique par entité (`order_id`, `customer_id`,
  `product_id`, `review_id`, `seller_id`).
- **Complétude** : colonnes obligatoires non nulles (`not_null` sur les clés
  et champs métier critiques).
- **Domaine de valeurs** : `order_status` et `payment_type` restreints à une
  liste de valeurs autorisées (`accepted_values`).
- **Plage numérique** : `review_score` ∈ [1, 5], `price` strictement positif
  (`dbt_expectations.expect_column_values_to_be_between`).
- **Intégrité référentielle** : `silver_order_items.order_id` → `silver_orders.order_id`,
  `silver_order_items.product_id` → `silver_products.product_id`,
  `silver_reviews.order_id` → `silver_orders.order_id`,
  `silver_payments.order_id` → `silver_orders.order_id`
  (tests `relationships`).

### Gold (agrégée, full-refresh)
- **Unicité de la clé d'agrégation** : une ligne par `customer_unique_id`
  (`gold_customer_rfm`), par `product_id` (`gold_product_performance`), par
  `seller_id` (`gold_seller_ranking`).
- **Intégrité référentielle vers Silver** : chaque clé d'agrégation Gold doit
  exister dans la table Silver correspondante (tests `relationships`).
- **Target ML valide** : `gold_reviews_features.satisfied` ∈ {0, 1}, dérivée
  déterministe de `review_score >= 4`.

### Règles métier custom (`dbt_project/tests/*.sql`)
| Test | Règle |
|---|---|
| `assert_no_orphan_orders.sql` | Aucune commande sans ligne d'article associée |
| `assert_positive_revenue.sql` | Les revenus agrégés en Gold sont toujours ≥ 0 |
| `assert_score_range.sql` | `review_score` reste dans [1, 5] à travers les couches |

---

## 4. Politique d'évolution du schéma

1. **Ajout de colonne** : autorisé sans coordination préalable en Bronze
   (dlt infère automatiquement le nouveau champ). En Silver/Gold, toute
   nouvelle colonne exposée doit être documentée dans `docs/data_dictionary.md`
   et couverte par au moins un test `not_null` ou `accepted_values` si elle
   sert de clé ou de dimension catégorielle.
2. **Suppression de colonne** : nécessite une revue de code — vérifier
   qu'aucun modèle dbt aval, aucune feature ML (`ml/training/features.py`)
   ni endpoint API (`api/schemas.py`) n'en dépend avant de la retirer.
3. **Renommage de colonne** : traité comme suppression + ajout ; interdit de
   renommer silencieusement une colonne consommée par la couche Gold ou par
   le feature set ML sans mettre à jour `docs/data_dictionary.md` et les tests
   associés dans la même PR.
4. **Changement de type** : doit rester rétro-compatible avec les modèles
   Silver qui castent déjà les types bruts (`safe_cast_date`, cast explicites) ;
   tout changement incompatible doit être signalé dans la description de la PR.
5. **Nouvelle source** : suit le même schéma de contrat que ci-dessus —
   colonnes obligatoires, type attendu, et ajout d'un nouveau pipeline dlt
   dédié (cf. convention établie en Sprint 1, un pipeline par entité).

Toute violation de ces règles est censée être détectée par le job CI
`test-dbt` (échec de `dbt build` si un test du data contract échoue).
