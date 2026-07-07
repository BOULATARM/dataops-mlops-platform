{{ config(materialized='table', schema='bronze', tags=['bronze']) }}

SELECT * FROM {{ source('bronze', 'raw_reviews') }}
