{{ config(materialized='table', schema='gold', tags=['gold']) }}

WITH products AS (
    SELECT product_id, product_category_name_english
    FROM {{ ref('silver_products') }}
),

items AS (
    SELECT order_id, product_id, seller_id, price, freight_value, total_item_value
    FROM {{ ref('silver_order_items') }}
),

orders AS (
    SELECT order_id, order_status
    FROM {{ ref('silver_orders') }}
    WHERE order_status = 'delivered'
),

reviews AS (
    SELECT order_id, review_score
    FROM {{ ref('silver_reviews') }}
),

item_orders AS (
    SELECT i.*, o.order_status
    FROM items AS i
    JOIN orders AS o ON i.order_id = o.order_id
),

reviews_per_order AS (
    SELECT order_id, AVG(review_score) AS avg_score
    FROM reviews
    GROUP BY order_id
)

SELECT
    p.product_id,
    p.product_category_name_english                                 AS category,
    COUNT(DISTINCT io.order_id)                                     AS total_orders,
    COUNT(*)                                                        AS total_items_sold,
    SUM(io.price)                                                   AS total_revenue,
    AVG(io.price)                                                   AS avg_unit_price,
    SUM(io.freight_value)                                           AS total_freight,
    SUM(io.total_item_value)                                        AS total_gmv,
    AVG(r.avg_score)                                                AS avg_review_score,
    COUNT(r.order_id)                                               AS total_reviewed_orders
FROM products AS p
LEFT JOIN item_orders AS io ON p.product_id = io.product_id
LEFT JOIN reviews_per_order AS r ON io.order_id = r.order_id
GROUP BY 1, 2
