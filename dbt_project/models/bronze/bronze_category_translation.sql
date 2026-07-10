{{ config(materialized='view') }}

SELECT *
FROM {{ source('bronze', 'product_category_name_translation') }}