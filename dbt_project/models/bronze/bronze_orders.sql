-- Bronze: raw orders — vue directe sur la table dlt, aucune transformation
-- Modèle complet généré à l'Étape 3
{{ config(materialized='table', schema='bronze', tags=['bronze']) }}

SELECT * FROM {{ source('bronze', 'raw_orders') }}
