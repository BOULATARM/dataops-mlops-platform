{{ config(materialized='table', schema='silver', tags=['silver']) }}

WITH source AS (
    SELECT * FROM {{ ref('bronze_sellers') }}
),

casted AS (
    SELECT
        seller_id,
        TRIM(seller_zip_code_prefix)    AS seller_zip_code_prefix,
        LOWER(TRIM(seller_city))        AS seller_city,
        UPPER(TRIM(seller_state))       AS seller_state,
        _loaded_at,
        _source_file,
        _batch_id
    FROM source
    WHERE seller_id IS NOT NULL
),

deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY seller_id
            ORDER BY _loaded_at DESC
        ) AS _rn
    FROM casted
)

SELECT
    seller_id,
    seller_zip_code_prefix,
    seller_city,
    seller_state,
    _loaded_at,
    _source_file,
    _batch_id
FROM deduped
WHERE _rn = 1
