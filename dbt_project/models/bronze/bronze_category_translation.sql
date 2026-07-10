{{ config(materialized='view') }}

SELECT *
FROM {{ source('bronze', 'raw_category_translation') }}