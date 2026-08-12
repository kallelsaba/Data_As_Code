from airflow import DAG
from airflow.operators.python import PythonOperator
import pendulum
import trino
from airflow.sdk import Asset

bronze_dataset = Asset("s3://bronze/")

local_tz = pendulum.timezone("Africa/Tunis")

TABLES = {
    "geolocation": {
        "location": "s3a://bronze/csv/",
        "format": "CSV",
        "skip_header": True,
        "columns": """
            geolocation_zip_code_prefix VARCHAR,
            geolocation_lat DOUBLE,
            geolocation_lng DOUBLE,
            geolocation_city VARCHAR,
            geolocation_state VARCHAR
        """
    },
    "customers": {
        "location": "s3a://bronze/mockoon/customers/",
        "format": "JSON",
        "columns": """
            customer_id VARCHAR,
            customer_unique_id VARCHAR,
            customer_zip_code_prefix VARCHAR,
            customer_city VARCHAR,
            customer_state VARCHAR
        """
    },
    "orders": {
        "location": "s3a://bronze/mockoon/orders/",
        "format": "JSON",
        "columns": """
            order_id VARCHAR,
            customer_id VARCHAR,
            order_status VARCHAR,
            order_purchase_timestamp TIMESTAMP,
            order_approved_at TIMESTAMP,
            order_delivered_carrier_date TIMESTAMP,
            order_delivered_customer_date TIMESTAMP,
            order_estimated_delivery_date TIMESTAMP
        """
    },
    "order_items": {
        "location": "s3a://bronze/mockoon/order_items/",
        "format": "JSON",
        "columns": """
            order_id VARCHAR,
            order_item_id INTEGER,
            product_id VARCHAR,
            seller_id VARCHAR,
            shipping_limit_date TIMESTAMP,
            price DOUBLE,
            freight_value DOUBLE
        """
    },
    "products": {
        "location": "s3a://bronze/sftp/products/",
        "format": "CSV",
        "skip_header": True,
        "columns": """
            product_id VARCHAR,
            product_category_name VARCHAR,
            product_name_lenght INTEGER,
            product_description_lenght INTEGER,
            product_photos_qty INTEGER,
            product_weight_g DOUBLE,
            product_length_cm DOUBLE,
            product_height_cm DOUBLE,
            product_width_cm DOUBLE
        """
    },
    "sellers": {
        "location": "s3a://bronze/sftp/sellers/",
        "format": "CSV",
        "skip_header": True,
        "columns": """
            seller_id VARCHAR,
            seller_zip_code_prefix VARCHAR,
            seller_city VARCHAR,
            seller_state VARCHAR
        """
    },
    "order_payments": {
        "location": "s3a://bronze/smb/order_payments/",
        "format": "CSV",
        "skip_header": True,
        "columns": """
            order_id VARCHAR,
            payment_sequential INTEGER,
            payment_type VARCHAR,
            payment_installments INTEGER,
            payment_value DOUBLE
        """
    },
    "order_reviews": {
        "location": "s3a://bronze/smb/order_reviews/",
        "format": "CSV",
        "skip_header": True,
        "columns": """
            review_id VARCHAR,
            order_id VARCHAR,
            review_score INTEGER,
            review_comment_title VARCHAR,
            review_comment_message VARCHAR,
            review_creation_date TIMESTAMP,
            review_answer_timestamp TIMESTAMP
        """
    },
}

def create_hive_schema():
    conn = trino.dbapi.connect(
        host="trino",
        port=8080,
        user="airflow",
        catalog="hive"
    )
    cur = conn.cursor()
    cur.execute("CREATE SCHEMA IF NOT EXISTS hive.bronze WITH (location = 's3a://bronze/')")
    cur.fetchall()

def create_external_tables():
    conn = trino.dbapi.connect(host="trino", port=8080, user="airflow", catalog="hive")
    cur = conn.cursor()
    for name, cfg in TABLES.items():
        with_clause = f"external_location = '{cfg['location']}', format = '{cfg['format']}'"
        if cfg.get("skip_header"):
            with_clause += ", skip_header_line_count = 1"
        query = f"""
            CREATE TABLE IF NOT EXISTS hive.bronze.{name} (
                {cfg['columns']}
            )
            WITH ({with_clause})
        """
        cur.execute(query)
        cur.fetchall()

with DAG(
    dag_id="silver_transformation",
    start_date=pendulum.datetime(2026, 8, 11, tz=local_tz),
    schedule=[bronze_dataset],
    catchup=False,
    is_paused_upon_creation=False,
    tags=["silver", "transformation"],
) as dag:
    t1 = PythonOperator(task_id="create_hive_schema", python_callable=create_hive_schema)
    t2 = PythonOperator(task_id="create_external_tables", python_callable=create_external_tables)
    t1 >> t2
