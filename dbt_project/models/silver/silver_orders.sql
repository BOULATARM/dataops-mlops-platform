{{ config(materialized='table', schema='silver', tags=['silver']) }}

WITH source AS (
    SELECT * FROM {{ ref('bronze_orders') }}
),

casted AS (
    SELECT
        order_id,
        customer_id,
        LOWER(TRIM(order_status))                                   AS order_status,
        TRY_CAST(order_purchase_timestamp   AS TIMESTAMP)           AS order_purchase_timestamp,
        TRY_CAST(order_approved_at          AS TIMESTAMP)           AS order_approved_at,
        TRY_CAST(order_delivered_carrier_date  AS TIMESTAMP)        AS order_delivered_carrier_date,
        TRY_CAST(order_delivered_customer_date AS TIMESTAMP)        AS order_delivered_customer_date,
        TRY_CAST(order_estimated_delivery_date AS TIMESTAMP)        AS order_estimated_delivery_date,
        _loaded_at,
        _source_file,
        _batch_id
    FROM source
    WHERE order_id    IS NOT NULL
      AND customer_id IS NOT NULL
),

deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY _loaded_at DESC
        ) AS _rn
    FROM casted
)

SELECT
    order_id,
    customer_id,
    order_status,
    order_purchase_timestamp,
    order_approved_at,
    order_delivered_carrier_date,
    order_delivered_customer_date,
    order_estimated_delivery_date,
    _loaded_at,
    _source_file,
    _batch_id
FROM deduped
WHERE _rn = 1
