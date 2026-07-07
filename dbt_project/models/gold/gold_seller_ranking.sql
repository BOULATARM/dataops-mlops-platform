{{ config(materialized='table', schema='gold', tags=['gold']) }}

WITH sellers AS (
    SELECT seller_id, seller_city, seller_state
    FROM {{ ref('silver_sellers') }}
),

items AS (
    SELECT order_id, seller_id, price, freight_value, total_item_value
    FROM {{ ref('silver_order_items') }}
),

orders AS (
    SELECT order_id, order_purchase_timestamp,
           order_delivered_customer_date
    FROM {{ ref('silver_orders') }}
    WHERE order_status = 'delivered'
),

reviews AS (
    SELECT order_id, review_score
    FROM {{ ref('silver_reviews') }}
),

item_orders AS (
    SELECT
        i.seller_id,
        i.order_id,
        i.price,
        i.freight_value,
        i.total_item_value,
        o.order_purchase_timestamp,
        o.order_delivered_customer_date
    FROM items AS i
    JOIN orders AS o ON i.order_id = o.order_id
),

review_scores AS (
    SELECT r.order_id, AVG(r.review_score) AS avg_score
    FROM reviews AS r
    GROUP BY r.order_id
)

SELECT
    s.seller_id,
    s.seller_city,
    s.seller_state,
    COUNT(DISTINCT io.order_id)                                     AS total_orders,
    COUNT(*)                                                        AS total_items_sold,
    SUM(io.price)                                                   AS total_revenue,
    AVG(io.price)                                                   AS avg_item_price,
    SUM(io.total_item_value)                                        AS total_gmv,
    ROUND(AVG(rs.avg_score), 2)                                     AS avg_review_score,
    COUNT(rs.order_id)                                              AS total_reviewed_orders,
    ROUND(
        AVG(
            CASE
                WHEN io.order_delivered_customer_date IS NOT NULL
                     AND io.order_purchase_timestamp IS NOT NULL
                THEN DATEDIFF('day',
                         io.order_purchase_timestamp::DATE,
                         io.order_delivered_customer_date::DATE)
                ELSE NULL
            END
        ), 1
    )                                                               AS avg_delivery_days,
    DENSE_RANK() OVER (ORDER BY SUM(io.price) DESC)                 AS revenue_rank
FROM sellers AS s
LEFT JOIN item_orders AS io ON s.seller_id = io.seller_id
LEFT JOIN review_scores AS rs ON io.order_id = rs.order_id
GROUP BY 1, 2, 3
