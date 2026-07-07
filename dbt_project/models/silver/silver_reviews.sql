{{ config(materialized='table', schema='silver', tags=['silver']) }}

WITH source AS (
    SELECT * FROM {{ ref('bronze_reviews') }}
),

casted AS (
    SELECT
        review_id,
        order_id,
        TRY_CAST(review_score AS INTEGER)                           AS review_score,
        NULLIF(TRIM(review_comment_title),   '')                    AS review_comment_title,
        NULLIF(TRIM(review_comment_message), '')                    AS review_comment_message,
        TRY_CAST(review_creation_date    AS TIMESTAMP)              AS review_creation_date,
        TRY_CAST(review_answer_timestamp AS TIMESTAMP)              AS review_answer_timestamp,
        _loaded_at,
        _source_file,
        _batch_id
    FROM source
    WHERE review_id IS NOT NULL
      AND order_id  IS NOT NULL
      AND TRY_CAST(review_score AS INTEGER) BETWEEN 1 AND 5
),

deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY review_id
            ORDER BY _loaded_at DESC
        ) AS _rn
    FROM casted
)

SELECT
    review_id,
    order_id,
    review_score,
    review_comment_title,
    review_comment_message,
    review_creation_date,
    review_answer_timestamp,
    _loaded_at,
    _source_file,
    _batch_id
FROM deduped
WHERE _rn = 1
