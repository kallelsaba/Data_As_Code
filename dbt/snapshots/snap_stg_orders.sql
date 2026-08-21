{% snapshot snap_stg_orders %}

{{
    config(
        target_schema='snapshots',
        unique_key="order_id || '-' || CAST(order_item_id AS VARCHAR)",
        strategy='timestamp',
        updated_at='CAST(_ingestion_date AS TIMESTAMP)'
    )
}}

SELECT
    *,
    CAST(_ingestion_date AS TIMESTAMP) AS snapshot_updated_at
FROM {{ ref('stg_orders') }}

{% endsnapshot %}
