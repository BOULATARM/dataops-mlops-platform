-- Test custom : le prix unitaire dans les items de commande doit être > 0
SELECT order_id, product_id, price
FROM {{ ref('silver_order_items') }}
WHERE price <= 0
