{{ config(materialized='table', schema='silver', tags=['silver']) }}

WITH source AS (
    SELECT * FROM {{ ref('bronze_order_items') }}
),

casted AS (
    SELECT
        order_id,
        TRY_CAST(order_item_id    AS INTEGER)                       AS order_item_id,
        product_id,
        seller_id,
        TRY_CAST(shipping_limit_date AS TIMESTAMP)                  AS shipping_limit_date,
        TRY_CAST(price            AS DOUBLE)                        AS price,
        TRY_CAST(freight_value    AS DOUBLE)                        AS freight_value,
        _loaded_at,
        _source_file,
        _batch_id
    FROM source
    WHERE order_id   IS NOT NULL
      AND product_id IS NOT NULL
      AND seller_id  IS NOT NULL
      AND TRY_CAST(price AS DOUBLE) > 0
)

SELECT
    order_id,
    order_item_id,
    product_id,
    seller_id,
    shipping_limit_date,
    price,
    freight_value,
    price + freight_value                                           AS total_item_value,
    _loaded_at,
    _source_file,
    _batch_id
FROM casted
