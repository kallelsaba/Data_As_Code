from airflow import DAG
from airflow.operators.python import PythonOperator
import pendulum
import trino
from airflow.sdk import Asset
from airflow.operators.bash import BashOperator
import psycopg2
import requests

bronze_dataset = Asset("s3://bronze/")

local_tz = pendulum.timezone("Africa/Tunis")

TABLES = {
    "geolocation": {
        "location": "s3a://bronze/csv/",
        "format": "CSV",
        "skip_header": True,
        "columns": """
            geolocation_zip_code_prefix VARCHAR,
            geolocation_lat VARCHAR,
            geolocation_lng VARCHAR,
            geolocation_city VARCHAR,
            geolocation_state VARCHAR,
            _ingestion_date VARCHAR
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
            customer_state VARCHAR,
            _ingestion_date DATE
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
            order_estimated_delivery_date TIMESTAMP,
            _ingestion_date DATE
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
            freight_value DOUBLE,
            _ingestion_date DATE
        """
    },
    "products": {
        "location": "s3a://bronze/sftp/products/",
        "format": "CSV",
        "skip_header": True,
        "columns": """
            product_id VARCHAR,
            product_category_name VARCHAR,
            product_name_lenght VARCHAR,
            product_description_lenght VARCHAR,
            product_photos_qty VARCHAR,
            product_weight_g VARCHAR,
            product_length_cm VARCHAR,
            product_height_cm VARCHAR,
            product_width_cm VARCHAR,
            _ingestion_date DATE
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
            seller_state VARCHAR,
            _ingestion_date DATE
        """
    },
    "order_payments": {
        "location": "s3a://bronze/smb/order_payments/",
        "format": "CSV",
        "skip_header": True,
        "columns": """
            order_id VARCHAR,
            payment_sequential VARCHAR,
            payment_type VARCHAR,
            payment_installments VARCHAR,
            payment_value VARCHAR,
            _ingestion_date DATE
        """
    },
    "order_reviews": {
        "location": "s3a://bronze/smb/order_reviews/",
        "format": "CSV",
        "skip_header": True,
        "columns": """
            review_id VARCHAR,
            order_id VARCHAR,
            review_score VARCHAR,
            review_comment_title VARCHAR,
            review_comment_message VARCHAR,
            review_creation_date VARCHAR,
            review_answer_timestamp VARCHAR,
            _ingestion_date DATE
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

def create_snapshots_schema():
    conn = psycopg2.connect(host="postgres", user="dataops", password="dataops", dbname="dataops")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("CREATE SCHEMA IF NOT EXISTS snapshots;")
    cur.close()
    conn.close()

def refresh_superset_cache():
    session = requests.Session()
    resp = session.post(
        "http://superset:8088/api/v1/security/login",
        json={"username": "admin", "password": "admin", "provider": "db", "refresh": True},
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    session.headers.update({"Authorization": f"Bearer {token}"})

    csrf = session.get("http://superset:8088/api/v1/security/csrf_token/")
    csrf.raise_for_status()
    session.headers.update({
        "X-CSRFToken": csrf.json()["result"],
        "Referer": "http://superset:8088",
    })

    resp = session.put("http://superset:8088/api/v1/dashboard/3/cache_refresh")
    resp.raise_for_status()


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
    t_clean_run = BashOperator(
    	task_id="clean_before_run",
    	bash_command=(
        	"docker exec trino trino --execute "
        	"\"DROP TABLE IF EXISTS postgres.silver.stg_orders\"; "
        	"docker exec trino trino --execute "
        	"\"DROP TABLE IF EXISTS postgres.silver.stg_orders__dbt_tmp\"; "
        	"docker exec trino trino --execute "
        	"\"DROP TABLE IF EXISTS postgres.silver.stg_orders__dbt_backup\"; "
    	)
    )

    t3 = BashOperator(
        task_id="run_dbt_stg_orders",
        bash_command="docker exec dbt dbt run --select stg_orders"
    )

    t_snap_schema = PythonOperator(task_id="create_snapshots_schema", python_callable=create_snapshots_schema)


    t4 = BashOperator(task_id="run_dbt_scd2", bash_command="docker exec dbt dbt run --select snap_stg_orders")


    t5 = BashOperator(
    	task_id="om_ingest_trino",
    	bash_command="docker exec om-ingestion metadata ingest -c /ingestion/trino_service.yaml"
    )
    t6 = BashOperator(
    	task_id="om_ingest_postgres",
    	bash_command="docker exec om-ingestion metadata ingest -c /ingestion/postgres_service.yaml"
    )
    t7 = BashOperator(
    	task_id="om_ingest_dbt",
    	bash_command="docker exec om-ingestion metadata ingest -c /ingestion/dbt_service.yaml"
    )


    t1 >> t2 >> t_clean_run >> t3 >> t_snap_schema >> t4  >> t5 >> t6 >> t7 
