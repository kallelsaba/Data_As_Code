from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import date
from datetime import datetime
import requests, boto3, paramiko, io
import pendulum
from smbclient import register_session, listdir, open_file
from airflow.sdk import Asset
import json
import csv
import io

bronze_dataset = Asset("s3://bronze/")

local_tz = pendulum.timezone("Africa/Tunis")

MINIO = boto3.client("s3", endpoint_url="http://minio:9000",
                      aws_access_key_id="admin", aws_secret_access_key="password123")

SOURCES_DIR = "/opt/airflow/sources"

today = date.today()
prefix = f"{today.year}/{today.month:02d}/{today.day:02d}"
ingestion_date_str = today.isoformat()

def ingest_mockoon():
    for t in ["orders", "order_items", "customers"]:
        data = requests.get(f"http://mockoon:3000/{t}").json()
        for record in data:
            record["_ingestion_date"] = ingestion_date_str
        ndjson = "\n".join(json.dumps(record) for record in data)
        MINIO.put_object(Bucket="bronze", Key=f"mockoon/{t}/{prefix}/{t}.json", Body=ndjson.encode("utf-8"))

def ingest_sftp():
    ssh = paramiko.Transport(("sftp", 22))
    ssh.connect(username="dataops", password="dataops")
    sftp = paramiko.SFTPClient.from_transport(ssh)
    for f in sftp.listdir("/upload"):
        buf = io.BytesIO()
        sftp.getfo(f"/upload/{f}", buf)
        raw_bytes = buf.getvalue()

        enriched_bytes = add_ingestion_date_to_csv(raw_bytes)

        table_name = f.replace("olist_", "").replace("_dataset.csv", "")
        MINIO.put_object(Bucket="bronze", Key=f"sftp/{table_name}/{prefix}/{table_name}.csv", Body=enriched_bytes)
    sftp.close()
    ssh.close()

def ingest_smb():
    register_session(
        "smb",
        username="dataops",
        password="dataops"
    )

    for filename in listdir(r"\\smb\share"):
        with open_file(
            rf"\\smb\share\{filename}",
            mode="rb"
        ) as f:
            data = f.read()

        enriched_bytes = add_ingestion_date_to_csv(data)

        table_name = filename.replace("olist_", "").replace("_dataset.csv", "")
        MINIO.put_object(Bucket="bronze", Key=f"smb/{table_name}/{prefix}/{table_name}.csv", Body=enriched_bytes)

def add_ingestion_date_to_csv(csv_bytes: bytes) -> bytes:
    """Ajoute une colonne _ingestion_date à un CSV brut (bytes -> bytes)."""
    text = csv_bytes.decode("utf-8")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    header = rows[0] + ["_ingestion_date"]
    new_rows = [header]
    for row in rows[1:]:
        new_rows.append(row + [ingestion_date_str])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(new_rows)
    return output.getvalue().encode("utf-8")

def ingest_csv():
    path = f"{SOURCES_DIR}/csv/olist_geolocation_dataset.csv"
    with open(path, "rb") as f:
        raw_bytes = f.read()

        enriched_bytes = add_ingestion_date_to_csv(raw_bytes)
        MINIO.put_object(Bucket="bronze", Key=f"csv/{prefix}/geolocation.csv", Body=enriched_bytes)


with DAG(
    dag_id="bronze_ingestion",
    start_date=pendulum.datetime(2026, 8, 11, tz=local_tz),
    schedule="26 20 * * *",
    catchup=False,
    is_paused_upon_creation=False,
    tags=["bronze", "ingestion"],
) as dag:
    PythonOperator(task_id="ingest_mockoon", python_callable=ingest_mockoon, outlets=[bronze_dataset])
    PythonOperator(task_id="ingest_sftp", python_callable=ingest_sftp, outlets=[bronze_dataset])
    PythonOperator(task_id="ingest_smb", python_callable=ingest_smb, outlets=[bronze_dataset])
    PythonOperator(task_id="ingest_csv", python_callable=ingest_csv, outlets=[bronze_dataset])
