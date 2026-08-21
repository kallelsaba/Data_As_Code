{{ config(
    materialized='incremental',
    unique_key='dbt_scd_id',
    on_schema_change='sync_all_columns',
    views_enabled=false
) }}

WITH source_data AS (
    SELECT
        *,
        CAST(_ingestion_date AS TIMESTAMP) AS updated_at,

        to_hex(
            md5(
                to_utf8(
                    CONCAT(
                        CAST(order_id AS VARCHAR),
                        '-',
                        CAST(order_item_id AS VARCHAR),
                        '-',
                        CAST(_ingestion_date AS VARCHAR)
                    )
                )
            )
        ) AS dbt_scd_id

    FROM {{ ref('stg_orders') }}
)

{% if is_incremental() %}

, current_data AS (
    SELECT *
    FROM {{ this }}
    WHERE dbt_valid_to IS NULL
),

changes AS (
    SELECT s.*
    FROM source_data s
    LEFT JOIN current_data c
        ON s.order_id = c.order_id
        AND s.order_item_id = c.order_item_id
    WHERE c.dbt_scd_id IS NULL
       OR s.updated_at > c.updated_at
)

SELECT
    *,
    updated_at AS dbt_valid_from,
    CAST(NULL AS TIMESTAMP) AS dbt_valid_to,
    FALSE AS dbt_is_deleted
FROM changes

{% else %}

SELECT
    *,
    updated_at AS dbt_valid_from,
    CAST(NULL AS TIMESTAMP) AS dbt_valid_to,
    FALSE AS dbt_is_deleted
FROM source_data

{% endif %}
