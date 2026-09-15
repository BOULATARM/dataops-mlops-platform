{% docs __overview__ %}

# Olist Medallion — dbt Project

Projet dbt implémentant l'architecture médaillon (Bronze / Silver / Gold)  
sur les données e-commerce Olist, stockées dans DuckDB.

## Couches

### Bronze
Tables miroir des données brutes ingérées par dlt. Aucune transformation —  
les données sont stockées telles quelles avec les métadonnées d'ingestion.

### Silver
Données nettoyées, dédupliquées et typées. Chaque modèle Silver correspond  
à une entité métier validée avec des tests dbt (not_null, unique, etc.).

### Gold
Marts métier et feature sets prêts à l'emploi pour le BI et le ML.  
Les agrégats sont recalculés quotidiennement (full-refresh).

## Lineage

[Télécharger la documentation générée dans GitHub Actions](https://github.com/BOULATARM/dataops-mlops-platform/actions/workflows/ci.yml)
: artifact `dbt-docs-<commit>`, conservé 30 jours, généré sur les fixtures CI.
Extraire puis servir avec `python -m http.server 8080` pour explorer le graphe.

```
bronze_* → silver_* → gold_orders_summary
                     → gold_customer_rfm
                     → gold_product_performance
                     → gold_seller_ranking
                     → gold_reviews_features  →  ML (SatisfactionClassifier)
```

{% enddocs %}
