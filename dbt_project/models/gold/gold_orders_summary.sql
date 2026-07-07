{{ config(materialized='table', schema='gold', tags=['gold']) }}

WITH orders AS (
    SELECT * FROM {{ ref('silver_orders') }}
),

customers AS (
    SELECT customer_id, customer_unique_id, customer_city, customer_state
    FROM {{ ref('silver_customers') }}
),

items AS (
    SELECT order_id, price, freight_value, total_item_value
    FROM {{ ref('silver_order_items') }}
),

order_totals AS (
    SELECT
        order_id,
        COUNT(*)                    AS total_items,
        SUM(price)                  AS total_product_revenue,
        SUM(freight_value)          AS total_freight_revenue,
        SUM(total_item_value)       AS total_order_value
    FROM items
    GROUP BY order_id
)

SELECT
    c.customer_unique_id,
    c.customer_city,
    c.customer_state,
    DATE_TRUNC('month', o.order_purchase_timestamp)::DATE           AS order_month,
    COUNT(DISTINCT o.order_id)                                      AS total_orders,
    SUM(ot.total_items)                                             AS total_items,
    SUM(ot.total_order_value)                                       AS total_revenue,
    AVG(ot.total_order_value)                                       AS avg_order_value,
    SUM(ot.total_product_revenue)                                   AS total_product_revenue,
    SUM(ot.total_freight_revenue)                                   AS total_freight_revenue,
    COUNT(DISTINCT CASE WHEN o.order_status = 'delivered'
                        THEN o.order_id END)                        AS delivered_orders,
    COUNT(DISTINCT CASE WHEN o.order_status = 'canceled'
                        THEN o.order_id END)                        AS canceled_orders
FROM orders AS o
JOIN customers AS c ON o.customer_id = c.customer_id
JOIN order_totals AS ot ON o.order_id = ot.order_id
WHERE o.order_purchase_timestamp IS NOT NULL
GROUP BY 1, 2, 3, 4
