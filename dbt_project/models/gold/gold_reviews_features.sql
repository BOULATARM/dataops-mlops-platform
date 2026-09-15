{{ config(materialized='table', schema='gold', tags=['gold']) }}

-- Feature store pour le modèle ML de satisfaction (classification binaire)
-- Target: satisfied = 1 si review_score >= 4

WITH reviews AS (
    SELECT
        review_id,
        order_id,
        review_score,
        review_comment_message,
        review_creation_date
    FROM {{ ref('silver_reviews') }}
    WHERE review_score IS NOT NULL
),

orders AS (
    SELECT
        order_id,
        customer_id,
        order_status,
        order_purchase_timestamp,
        order_delivered_customer_date,
        order_estimated_delivery_date
    FROM {{ ref('silver_orders') }}
),

-- Paiement dominant (valeur la plus élevée) par commande
payments_ranked AS (
    SELECT
        order_id,
        payment_type,
        payment_value,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY payment_value DESC
        ) AS rn
    FROM {{ ref('silver_payments') }}
),

top_payment AS (
    SELECT order_id, payment_type
    FROM payments_ranked
    WHERE rn = 1
)

SELECT
    r.review_id,
    r.order_id,

    -- ── Target ──────────────────────────────────────────────────────────────
    r.review_score,
    CASE WHEN r.review_score >= 4 THEN 1 ELSE 0 END                AS satisfied,

    -- ── Features texte ──────────────────────────────────────────────────────
    COALESCE(r.review_comment_message, '') AS review_comment_message,
    LENGTH(COALESCE(r.review_comment_message, ''))                  AS review_comment_length,
    CASE
        WHEN r.review_comment_message IS NOT NULL
             AND LENGTH(TRIM(r.review_comment_message)) > 0
        THEN TRUE
        ELSE FALSE
    END                                                             AS has_comment,

    -- ── Feature livraison ────────────────────────────────────────────────────
    -- Positif = livraison en retard, négatif = livraison anticipée
    CASE
        WHEN o.order_delivered_customer_date IS NOT NULL
             AND o.order_estimated_delivery_date IS NOT NULL
        THEN DATEDIFF(
                'day',
                o.order_estimated_delivery_date::DATE,
                o.order_delivered_customer_date::DATE
             )
        ELSE NULL
    END                                                             AS delivery_delay_days,

    -- ── Feature paiement (encodé en dur pour sklearn) ────────────────────────
    CASE
        WHEN LOWER(TRIM(COALESCE(tp.payment_type, ''))) IN (
            'credit_card',
            'boleto',
            'voucher',
            'debit_card'
        )
        THEN LOWER(TRIM(tp.payment_type))
        ELSE 'not_defined'
    END AS payment_type,

    CASE
        WHEN LOWER(TRIM(COALESCE(tp.payment_type, ''))) = 'credit_card'
            THEN 0
        WHEN LOWER(TRIM(COALESCE(tp.payment_type, ''))) = 'boleto'
            THEN 1
        WHEN LOWER(TRIM(COALESCE(tp.payment_type, ''))) = 'voucher'
            THEN 2
        WHEN LOWER(TRIM(COALESCE(tp.payment_type, ''))) = 'debit_card'
            THEN 3
        ELSE 4
    END AS payment_type_encoded,

    -- ── Métadonnées ──────────────────────────────────────────────────────────
    o.order_status,
    o.customer_id,
    r.review_creation_date,
    o.order_purchase_timestamp

FROM reviews AS r
LEFT JOIN orders AS o ON r.order_id = o.order_id
LEFT JOIN top_payment AS tp ON r.order_id = tp.order_id
