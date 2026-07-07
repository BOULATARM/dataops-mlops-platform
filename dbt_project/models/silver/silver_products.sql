{{ config(materialized='table', schema='silver', tags=['silver']) }}

WITH source AS (
    SELECT * FROM {{ ref('bronze_products') }}
),

category_trans AS (
    SELECT
        product_category_name,
        product_category_name_english
    FROM {{ ref('bronze_category_translation') }}
),

casted AS (
    SELECT
        p.product_id,
        TRIM(p.product_category_name)                               AS product_category_name,
        COALESCE(
            c.product_category_name_english,
            p.product_category_name
        )                                                           AS product_category_name_english,
        -- Note: colonne avec faute de frappe dans la source ("lenght")
        TRY_CAST(p.product_name_lenght        AS INTEGER)           AS product_name_length,
        TRY_CAST(p.product_description_lenght AS INTEGER)           AS product_description_length,
        TRY_CAST(p.product_photos_qty         AS INTEGER)           AS product_photos_qty,
        TRY_CAST(p.product_weight_g           AS DOUBLE)            AS product_weight_g,
        TRY_CAST(p.product_length_cm          AS DOUBLE)            AS product_length_cm,
        TRY_CAST(p.product_height_cm          AS DOUBLE)            AS product_height_cm,
        TRY_CAST(p.product_width_cm           AS DOUBLE)            AS product_width_cm,
        p._loaded_at,
        p._source_file,
        p._batch_id
    FROM source AS p
    LEFT JOIN category_trans AS c USING (product_category_name)
    WHERE p.product_id IS NOT NULL
),

deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY product_id
            ORDER BY _loaded_at DESC
        ) AS _rn
    FROM casted
)

SELECT
    product_id,
    product_category_name,
    product_category_name_english,
    product_name_length,
    product_description_length,
    product_photos_qty,
    product_weight_g,
    product_length_cm,
    product_height_cm,
    product_width_cm,
    _loaded_at,
    _source_file,
    _batch_id
FROM deduped
WHERE _rn = 1
