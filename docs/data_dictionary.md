# Dictionnaire de données — mlops-dataops-platform

Référentiel des tables et colonnes clés par couche du modèle médaillon (Bronze/Silver/Gold),
stocké dans DuckDB (`warehouse/duckdb/olist.duckdb`). Complète le data contract défini dans
les fichiers `schema.yml` de `dbt_project/models/*/`.

---

## Couche Bronze (schéma `bronze`)

Politique : append-only, aucune transformation. Chaque table porte les colonnes système
`_loaded_at` (timestamp d'ingestion dlt), `_source_file` (fichier source) et `_batch_id`
(UUID de l'exécution du pipeline).

| Table | Source | Colonnes clés |
|---|---|---|
| `raw_orders` | `olist_orders_dataset.csv` | `order_id` |
| `raw_customers` | `olist_customers_dataset.csv` | `customer_id`, `customer_unique_id` |
| `raw_order_items` | `olist_order_items_dataset.csv` | `order_id`, `order_item_id`, `product_id`, `seller_id`, `price`, `freight_value` |
| `raw_products` | `olist_products_dataset.csv` | `product_id` |
| `raw_reviews` | `olist_order_reviews_dataset.csv` | `review_id`, `order_id`, `review_score`, `review_comment_message` |
| `raw_payments` | `olist_order_payments_dataset.csv` | `order_id`, `payment_type`, `payment_value` |
| `raw_sellers` | `olist_sellers_dataset.csv` | `seller_id` |
| `raw_geolocation` | `olist_geolocation_dataset.csv` | `geolocation_zip_code_prefix`, `geolocation_lat/lng` |
| `raw_category_translation` | `product_category_name_translation.csv` | `product_category_name`, `product_category_name_english` |
| `raw_exchange_rates` | `exchange_rates_snapshot.json` | `currency_code`, `rate`, `base_currency`, `fetched_at` |
| `raw_products_json` | `products_sample.json` | `product_id`, `product_name`, `category`, `unit_price`, `unit_cost` |

---

## Couche Silver (schéma `silver`)

Politique : nettoyage, cast de types, déduplication sur clé naturelle, normalisation.

| Table | Description | Contraintes (data contract) |
|---|---|---|
| `silver_orders` | Commandes nettoyées, typées, dédupliquées | `order_id` not_null+unique · `customer_id` not_null · `order_status` ∈ {delivered, shipped, canceled, invoiced, processing, created, approved, unavailable} · `order_purchase_timestamp` not_null |
| `silver_customers` | Clients dédupliqués | `customer_id` not_null+unique · `customer_unique_id` not_null |
| `silver_products` | Produits avec traduction catégorie en anglais | `product_id` not_null+unique |
| `silver_reviews` | Avis clients avec score validé et texte nettoyé | `review_id` not_null+unique · `order_id` not_null · `review_score` not_null, compris entre 1 et 5 |
| `silver_payments` | Paiements avec type validé | `order_id` not_null · `payment_type` ∈ {credit_card, boleto, voucher, debit_card, not_defined} |
| `silver_sellers` | Vendeurs dédupliqués | `seller_id` not_null+unique |
| `silver_order_items` | Lignes de commande enrichies (join orders + products) | `order_id`/`product_id` not_null · `price` strictement positif |

---

## Couche Gold (schéma `gold`)

Politique : full-refresh quotidien, agrégats métier et feature set ML.

| Table | Description | Contraintes (data contract) |
|---|---|---|
| `gold_orders_summary` | KPIs commandes agrégés par client et par mois | `customer_unique_id` not_null · `order_month` not_null |
| `gold_customer_rfm` | Scoring RFM (Récence/Fréquence/Montant) par client | `customer_unique_id` not_null+unique |
| `gold_product_performance` | Revenus, volumes et notes moyennes par produit/catégorie | `product_id` not_null+unique |
| `gold_seller_ranking` | Performance vendeurs (délais, notes, CA, volume) | `seller_id` not_null+unique |
| `gold_reviews_features` | Feature set ML — classification satisfaction client | `review_id` not_null+unique · `satisfied` not_null, ∈ {0,1} · `review_score` not_null · `payment_type` not_null |

### Détail des colonnes de `gold_reviews_features` (feature set ML)

| Colonne | Type | Description |
|---|---|---|
| `satisfied` | int (0/1) | **Target** : `1` si `review_score >= 4`, sinon `0` |
| `review_score` | int (1-5) | Note brute laissée par le client |
| `delivery_delay_days` | float | Délai entre date de livraison estimée et réelle (négatif = livré en avance) |
| `has_comment` | bool | Présence ou non d'un commentaire textuel |
| `review_comment_length` | int | Nombre de caractères du commentaire (0 si absent) |
| `payment_type` | string | Type de paiement utilisé pour la commande associée |
| `payment_type_encoded` | int | Encodage one-hot / ordinal de `payment_type`, consommé par l'API `/predict` |

---

## Règles de qualité custom (`dbt_project/tests/*.sql`)

| Test | Objectif |
|---|---|
| `assert_no_orphan_orders.sql` | Vérifie qu'aucune commande Silver/Gold ne référence un `order_id` sans ligne d'article associée |
| `assert_positive_revenue.sql` | Vérifie que les montants de revenus agrégés en couche Gold sont toujours positifs |
| `assert_score_range.sql` | Vérifie que `review_score` reste dans l'intervalle valide [1, 5] à travers les couches |

---

## Notes

- Aucune table ne porte de SCD Type 2 — la couche Bronze est append-only, la Silver déduplique
  en gardant la dernière version connue par clé naturelle, la Gold est recalculée en full-refresh.
  Voir `docs/architecture.md` pour la justification de ce choix.
- Ce dictionnaire doit être mis à jour à chaque ajout/modification de colonne dans un modèle
  dbt Silver ou Gold (cf. action de sprint 2, `docs/agile/sprint_2.md`).
