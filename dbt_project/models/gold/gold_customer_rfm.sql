{{ config(materialized='table', schema='gold', tags=['gold']) }}

WITH orders AS (
    SELECT * FROM {{ ref('silver_orders') }}
    WHERE order_status = 'delivered'
      AND order_purchase_timestamp IS NOT NULL
),

customers AS (
    SELECT customer_id, customer_unique_id, customer_city, customer_state
    FROM {{ ref('silver_customers') }}
),

items AS (
    SELECT order_id, SUM(total_item_value) AS order_value
    FROM {{ ref('silver_order_items') }}
    GROUP BY order_id
),

rfm_base AS (
    SELECT
        c.customer_unique_id,
        MAX(o.order_purchase_timestamp)::DATE                       AS last_order_date,
        COUNT(DISTINCT o.order_id)                                  AS frequency,
        SUM(i.order_value)                                          AS monetary_value,
        AVG(i.order_value)                                          AS avg_order_value
    FROM orders AS o
    JOIN customers AS c ON o.customer_id = c.customer_id
    JOIN items AS i ON o.order_id = i.order_id
    GROUP BY 1
),

-- Ville/état les plus récents pour chaque customer_unique_id
last_location AS (
    SELECT DISTINCT ON (c.customer_unique_id)
        c.customer_unique_id,
        c.customer_city,
        c.customer_state
    FROM customers AS c
    JOIN orders AS o ON c.customer_id = o.customer_id
    ORDER BY c.customer_unique_id, o.order_purchase_timestamp DESC NULLS LAST
)

SELECT
    r.customer_unique_id,
    ll.customer_city,
    ll.customer_state,
    r.last_order_date,
    DATEDIFF('day', r.last_order_date, CURRENT_DATE)               AS recency_days,
    r.frequency,
    r.monetary_value,
    r.avg_order_value,
    -- Scores RFM bruts (1=meilleur pour R, 5=meilleur pour F et M)
    NTILE(5) OVER (ORDER BY DATEDIFF('day', r.last_order_date, CURRENT_DATE) DESC) AS r_score,
    NTILE(5) OVER (ORDER BY r.frequency ASC)                        AS f_score,
    NTILE(5) OVER (ORDER BY r.monetary_value ASC)                   AS m_score
FROM rfm_base AS r
JOIN last_location AS ll ON r.customer_unique_id = ll.customer_unique_id
