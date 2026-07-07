{{ config(materialized='table', schema='silver', tags=['silver']) }}

WITH source AS (
    SELECT * FROM {{ ref('bronze_payments') }}
),

casted AS (
    SELECT
        order_id,
        TRY_CAST(payment_sequential    AS INTEGER)                  AS payment_sequential,
        LOWER(TRIM(payment_type))                                   AS payment_type,
        TRY_CAST(payment_installments  AS INTEGER)                  AS payment_installments,
        TRY_CAST(payment_value         AS DOUBLE)                   AS payment_value,
        _loaded_at,
        _source_file,
        _batch_id
    FROM source
    WHERE order_id     IS NOT NULL
      AND payment_type IS NOT NULL
      AND TRY_CAST(payment_value AS DOUBLE) >= 0
)

SELECT
    order_id,
    payment_sequential,
    payment_type,
    payment_installments,
    payment_value,
    _loaded_at,
    _source_file,
    _batch_id
FROM casted
