from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import requests, boto3, paramiko, io
from smb.SMBConnection import SMBConnection
import pendulum

local_tz = pendulum.timezone("Africa/Tunis")

MINIO = boto3.client("s3", endpoint_url="http://minio:9000",
                      aws_access_key_id="admin", aws_secret_access_key="password123")

SOURCES_DIR = "/opt/airflow/sources"

def ingest_mockoon():
    for t in ["orders", "order_items", "customers"]:
        data = requests.get(f"http://mockoon:3000/{t}").content
        MINIO.put_object(Bucket="bronze", Key=f"mockoon/{t}.json", Body=data)

def ingest_sftp():
    ssh = paramiko.Transport(("sftp", 22))
    ssh.connect(username="dataops", password="dataops")
    sftp = paramiko.SFTPClient.from_transport(ssh)
    for f in sftp.listdir("/upload"):
        buf = io.BytesIO()
        sftp.getfo(f"/upload/{f}", buf)
        MINIO.put_object(Bucket="bronze", Key=f"sftp/{f}", Body=buf.getvalue())
    sftp.close()
    ssh.close()

def ingest_smb():
    conn = SMBConnection("dataops", "dataops", "airflow", "smb")
    conn.connect("smb", 445)
    for f in conn.listPath("share", "/"):
        if f.isDirectory:
            continue
        buf = io.BytesIO()
        conn.retrieveFile("share", f"/{f.filename}", buf)
        MINIO.put_object(Bucket="bronze", Key=f"smb/{f.filename}", Body=buf.getvalue())
    conn.close()

def ingest_csv():
    path = f"{SOURCES_DIR}/csv/olist_geolocation_dataset.csv"
    with open(path, "rb") as f:
        MINIO.put_object(Bucket="bronze", Key="csv/geolocation.csv", Body=f.read())

def ingest_datasets():
    path = f"{SOURCES_DIR}/datasets/product_category_name_translation.csv"
    with open(path, "rb") as f:
        MINIO.put_object(Bucket="bronze", Key="datasets/product_category_name_translation.csv", Body=f.read())

with DAG("ingestion_bronze", start_date=datetime(2026, 1, 1), schedule="20 18 * * *", catchup=False) as dag:
    PythonOperator(task_id="ingest_mockoon", python_callable=ingest_mockoon)
    PythonOperator(task_id="ingest_sftp", python_callable=ingest_sftp)
    PythonOperator(task_id="ingest_smb", python_callable=ingest_smb)
    PythonOperator(task_id="ingest_csv", python_callable=ingest_csv)
    PythonOperator(task_id="ingest_datasets", python_callable=ingest_datasets)
