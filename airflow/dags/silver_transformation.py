from airflow import DAG
from airflow.operators.python import PythonOperator
import pendulum
import trino
from airflow.datasets import Dataset

bronze_dataset = Dataset("s3://bronze/")

local_tz = pendulum.timezone("Africa/Tunis")

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

with DAG(
    dag_id="silver_transformation",
    start_date=pendulum.datetime(2026, 8, 11, tz=local_tz),
    schedule=[bronze_dataset],
    catchup=False,
    is_paused_upon_creation=False,
    tags=["silver", "transformation"],
) as dag:
    PythonOperator(
        task_id="create_hive_schema",
        python_callable=create_hive_schema
    )
