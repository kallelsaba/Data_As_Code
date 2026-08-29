
{{ config(
    materialized='table',
    unique_key=['order_id', 'order_item_id'],
    views_enabled=false,
    on_table_exists='drop'
) }}

{% if is_incremental() %}
{% set max_date_query %}
    SELECT MAX(_ingestion_date) FROM {{ this }}
{% endset %}
{% set max_date = run_query(max_date_query).columns[0].values()[0] %}
{% endif %}

-- ============================================================
-- ORDERS : cast timestamps (NULL conservé si non livré), statut standardisé
-- ============================================================
WITH orders_dedup AS (
    SELECT *,
        TRY_CAST(_ingestion_date AS DATE) AS ingestion_date_typed,
        ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY order_purchase_timestamp DESC) AS rn
    FROM {{ source('bronze', 'orders') }}
    WHERE order_id IS NOT NULL

    {% if is_incremental() and max_date %}
    AND TRY_CAST(_ingestion_date AS DATE) > DATE '{{ max_date }}'
    {% endif %}
),
orders_clean AS (
    SELECT
        order_id,
        customer_id,
        LOWER(TRIM(order_status)) AS order_status,
        order_purchase_timestamp,          -- NULL non remplacé : sémantique métier (non livré/non traité)
        order_approved_at,
        order_delivered_carrier_date,
        order_delivered_customer_date,
        order_estimated_delivery_date,
        ingestion_date_typed AS _ingestion_date
    FROM orders_dedup
    WHERE rn = 1
),

-- ============================================================
-- ORDER_ITEMS : grain pivot, validation numérique (>= 0)
-- ============================================================
order_items_dedup AS (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY order_id, order_item_id ORDER BY order_item_id) AS rn
    FROM {{ source('bronze', 'order_items') }}
    WHERE order_id IS NOT NULL
),
order_items_clean AS (
    SELECT
        order_id,
        order_item_id,
        product_id,
        seller_id,
        shipping_limit_date,
        CASE
            WHEN price >= 0
            THEN price
            ELSE NULL
        END AS price,

        CASE
            WHEN freight_value >= 0
            THEN freight_value
            ELSE NULL
        END AS freight_value
    FROM order_items_dedup
    WHERE rn = 1
),

-- ============================================================
-- CUSTOMERS : nettoyage ville/état (casse, espaces)
-- ============================================================
customers_dedup AS (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY customer_id) AS rn
    FROM {{ source('bronze', 'customers') }}
    WHERE customer_id IS NOT NULL
),
customers_clean AS (
    SELECT
        customer_id,
        customer_unique_id,
        TRIM(customer_zip_code_prefix) AS customer_zip_code_prefix,
        LOWER(TRIM(customer_city)) AS customer_city,
        UPPER(TRIM(customer_state)) AS customer_state
    FROM customers_dedup
    WHERE rn = 1
),

-- ============================================================
-- SELLERS : même nettoyage que customers
-- ============================================================
sellers_dedup AS (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY seller_id ORDER BY seller_id) AS rn
    FROM {{ source('bronze', 'sellers') }}
    WHERE seller_id IS NOT NULL
),
sellers_clean AS (
    SELECT
        seller_id,
        TRIM(seller_zip_code_prefix) AS seller_zip_code_prefix,
        LOWER(TRIM(seller_city)) AS seller_city,
        UPPER(TRIM(seller_state)) AS seller_state
    FROM sellers_dedup
    WHERE rn = 1
),

-- ============================================================
-- GEOLOCATION : agrégation obligatoire par zip (relation N:N)
-- ============================================================
geolocation_agg AS (
    SELECT
        geolocation_zip_code_prefix,
        AVG(CAST(NULLIF(geolocation_lat, '') AS DOUBLE)) AS avg_lat,
        AVG(CAST(NULLIF(geolocation_lng, '') AS DOUBLE)) AS avg_lng,
        LOWER(TRIM(ARBITRARY(geolocation_city))) AS geolocation_city,
        UPPER(TRIM(ARBITRARY(geolocation_state))) AS geolocation_state
    FROM {{ source('bronze', 'geolocation') }}
    WHERE geolocation_zip_code_prefix IS NOT NULL
    GROUP BY geolocation_zip_code_prefix
),

-- ============================================================
-- PRODUCTS : fallback catégorie 'outros', imputation dimensions
-- par médiane de la catégorie (pas médiane globale)
-- ============================================================
products_dedup AS (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY product_id) AS rn
    FROM {{ source('bronze', 'products') }}
    WHERE product_id IS NOT NULL
),
products_typed AS (
    SELECT
        product_id,
        COALESCE(NULLIF(LOWER(TRIM(product_category_name)), ''), 'outros') AS product_category_name,
        TRY_CAST(product_photos_qty AS INTEGER) AS product_photos_qty,
        NULLIF(TRY_CAST(product_weight_g AS DOUBLE), 0.0) AS product_weight_g,
        NULLIF(TRY_CAST(product_length_cm AS DOUBLE), 0.0) AS product_length_cm,
        NULLIF(TRY_CAST(product_height_cm AS DOUBLE), 0.0) AS product_height_cm,
        NULLIF(TRY_CAST(product_width_cm AS DOUBLE), 0.0) AS product_width_cm 
    FROM products_dedup
    WHERE rn = 1
),
category_medians AS (
    SELECT
        product_category_name,
        APPROX_PERCENTILE(product_weight_g, 0.5) AS median_weight_g,
        APPROX_PERCENTILE(product_length_cm, 0.5) AS median_length_cm,
        APPROX_PERCENTILE(product_height_cm, 0.5) AS median_height_cm,
        APPROX_PERCENTILE(product_width_cm, 0.5) AS median_width_cm
    FROM products_typed
    GROUP BY product_category_name
),
products_clean AS (
    SELECT
        p.product_id,
        p.product_category_name,
        p.product_photos_qty,
        COALESCE(p.product_weight_g, m.median_weight_g) AS product_weight_g,
        COALESCE(p.product_length_cm, m.median_length_cm) AS product_length_cm,
        COALESCE(p.product_height_cm, m.median_height_cm) AS product_height_cm,
        COALESCE(p.product_width_cm, m.median_width_cm) AS product_width_cm
    FROM products_typed p
    LEFT JOIN category_medians m ON p.product_category_name = m.product_category_name
),
products_final AS (
    SELECT *,
        product_length_cm * product_height_cm * product_width_cm AS volume_cm3
    FROM products_clean
),

-- ============================================================
-- PAYMENTS : agrégation obligatoire par order_id AVANT jointure
-- (paiement_value=0 avec payment_type='not_defined' conservé tel quel : légitime)
-- ============================================================
order_payments_dedup AS (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY order_id, payment_sequential ORDER BY payment_sequential) AS rn
    FROM {{ source('bronze', 'order_payments') }}
    WHERE order_id IS NOT NULL
),
order_payments_clean AS (
    SELECT
        order_id,
        TRY_CAST(payment_sequential AS INTEGER) AS payment_sequential,
        LOWER(TRIM(payment_type)) AS payment_type,
        TRY_CAST(payment_installments AS INTEGER) AS payment_installments,
        CASE WHEN TRY_CAST(payment_value AS DOUBLE) >= 0
             THEN TRY_CAST(payment_value AS DOUBLE)
             ELSE NULL
        END AS payment_value
    FROM order_payments_dedup
    WHERE rn = 1
),
order_payments_agg AS (
    SELECT
        order_id,
        SUM(payment_value) AS total_payment_value,
        COUNT(*) AS payment_count,
        MAX(payment_installments) AS max_installments,
        MAX(payment_type) AS payment_type
    FROM order_payments_clean
    GROUP BY order_id
),

-- ============================================================
-- REVIEWS : dédup (garder la plus récente), score validé 1-5,
-- commentaires NULL conservés + flag has_comment
-- ============================================================
order_reviews_dedup AS (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_creation_date DESC) AS rn
    FROM {{ source('bronze', 'order_reviews') }}
    WHERE order_id IS NOT NULL
),
order_reviews_clean AS (
    SELECT
        order_id,
        review_id,
        CASE WHEN TRY_CAST(review_score AS SMALLINT) BETWEEN 1 AND 5
             THEN TRY_CAST(review_score AS SMALLINT) ELSE NULL END AS review_score,
        review_comment_title,
        review_comment_message,
        (review_comment_message IS NOT NULL AND TRIM(review_comment_message) != '') AS has_comment,
        TRY_CAST(review_creation_date AS TIMESTAMP) AS review_creation_date,
        TRY_CAST(review_answer_timestamp AS TIMESTAMP) AS review_answer_timestamp
    FROM order_reviews_dedup
    WHERE rn = 1
),

-- ============================================================
-- GRAIN FINAL : commande x article (pivot), KPIs + délais logistiques
-- ============================================================
base AS (
    SELECT
        o.order_id,
        o.order_status,
        o.order_purchase_timestamp,
        o.order_approved_at,
        o.order_delivered_carrier_date,
        o.order_delivered_customer_date,
        o.order_estimated_delivery_date,
        o._ingestion_date,

        c.customer_id,
        c.customer_unique_id,
        c.customer_zip_code_prefix,
        c.customer_city,
        c.customer_state,
        cg.avg_lat AS customer_lat,
        cg.avg_lng AS customer_lng,

        oi.order_item_id,
        oi.price,
        oi.freight_value,
        oi.shipping_limit_date,

        pr.product_id,
        COALESCE(pr.product_category_name, 'outros') AS product_category_name,
        pr.product_weight_g,
        pr.product_length_cm,
        pr.product_height_cm,
        pr.product_width_cm,
        pr.volume_cm3,

        s.seller_id,
        s.seller_zip_code_prefix,
        s.seller_city,
        s.seller_state,
        sg.avg_lat AS seller_lat,
        sg.avg_lng AS seller_lng,

        pay.total_payment_value,
        pay.payment_count,
        pay.max_installments,
        pay.payment_type,

        rev.review_id,
        rev.review_score,
        rev.review_comment_title,
        rev.review_comment_message,
        rev.has_comment,
        rev.review_creation_date,
        rev.review_answer_timestamp

    FROM orders_clean o
    LEFT JOIN order_items_clean oi ON o.order_id = oi.order_id
    LEFT JOIN customers_clean c ON o.customer_id = c.customer_id
    LEFT JOIN geolocation_agg cg ON c.customer_zip_code_prefix = cg.geolocation_zip_code_prefix
    LEFT JOIN products_final pr ON oi.product_id = pr.product_id
    LEFT JOIN sellers_clean s ON oi.seller_id = s.seller_id
    LEFT JOIN geolocation_agg sg ON s.seller_zip_code_prefix = sg.geolocation_zip_code_prefix
    LEFT JOIN order_payments_agg pay ON o.order_id = pay.order_id   -- agrégé AVANT jointure
    LEFT JOIN order_reviews_clean rev ON o.order_id = rev.order_id  -- dédupliqué AVANT jointure
)

SELECT
    *,

    -- KPIs commande (fenêtrés sur order_id, pas de double comptage payments/reviews)
    SUM(price) OVER (PARTITION BY order_id) AS order_total_product_value,
    SUM(freight_value) OVER (PARTITION BY order_id) AS order_total_freight,
    SUM(price) OVER (PARTITION BY order_id) + SUM(freight_value) OVER (PARTITION BY order_id) AS order_total_value,
    COUNT(*) OVER (PARTITION BY order_id) AS items_count,
    COUNT(DISTINCT seller_id) OVER (PARTITION BY order_id) AS sellers_count,

    -- Dimensions temporelles
    EXTRACT(YEAR FROM order_purchase_timestamp) AS order_year,
    EXTRACT(MONTH FROM order_purchase_timestamp) AS order_month,
    DAY_OF_WEEK(order_purchase_timestamp) AS order_day_of_week,

    -- Performance logistique (NULL si étape non atteinte, jamais 0)
    DATE_DIFF('day', order_purchase_timestamp, order_approved_at) AS approval_delay_days,
    DATE_DIFF('day', order_approved_at, order_delivered_carrier_date) AS shipping_delay_days,
    DATE_DIFF('day', order_purchase_timestamp, order_delivered_customer_date) AS total_delivery_days,
    DATE_DIFF('day', order_estimated_delivery_date, order_delivered_customer_date) AS delivery_delay_days,
    CASE
        WHEN order_delivered_customer_date IS NULL THEN NULL
        WHEN order_delivered_customer_date <= order_estimated_delivery_date THEN TRUE
        ELSE FALSE
    END AS is_delivered_on_time,

    -- Satisfaction client
    CASE WHEN TRY_CAST(review_score AS SMALLINT) >= 4 THEN TRUE ELSE FALSE END AS is_positive_review,
    CASE WHEN TRY_CAST(review_score AS SMALLINT) <= 2 THEN TRUE ELSE FALSE END AS is_negative_review

FROM base
