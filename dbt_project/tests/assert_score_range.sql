-- Test custom : review_score doit être entre 1 et 5 inclus
SELECT review_id, review_score
FROM {{ ref('silver_reviews') }}
WHERE review_score NOT BETWEEN 1 AND 5
