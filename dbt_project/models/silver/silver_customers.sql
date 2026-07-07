{{ config(materialized='table', schema='silver', tags=['silver']) }}

WITH source AS (
    SELECT * FROM {{ ref('bronze_customers') }}
),

casted AS (
    SELECT
        customer_id,
        customer_unique_id,
        TRIM(customer_zip_code_prefix)      AS customer_zip_code_prefix,
        LOWER(TRIM(customer_city))          AS customer_city,
        UPPER(TRIM(customer_state))         AS customer_state,
        _loaded_at,
        _source_file,
        _batch_id
    FROM source
    WHERE customer_id        IS NOT NULL
      AND customer_unique_id IS NOT NULL
),

deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY _loaded_at DESC
        ) AS _rn
    FROM casted
)

SELECT
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state,
    _loaded_at,
    _source_file,
    _batch_id
FROM deduped
WHERE _rn = 1
