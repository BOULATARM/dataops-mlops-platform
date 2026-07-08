-- Test custom : tout order_id présent dans silver_order_items existe dans silver_orders
-- Retourne les lignes en erreur (0 ligne = test OK)
SELECT oi.order_id
FROM {{ ref('silver_order_items') }} AS oi
LEFT JOIN {{ ref('silver_orders') }} AS o ON oi.order_id = o.order_id
WHERE o.order_id IS NULL
