{% snapshot snap_stg_orders %}
{{
    config(
        target_schema='snapshots',
        unique_key='order_id || \'-\' || CAST(order_item_id AS VARCHAR)',
        strategy='timestamp',
        updated_at='_ingestion_date',
    )
}}
SELECT * FROM {{ ref('stg_orders') }}
{% endsnapshot %}
