from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import requests, boto3, paramiko, io
# from smb.SMBConnection import SMBConnection ...
import pendulum
from smbclient import register_session, listdir, open_file

local_tz = pendulum.timezone("Africa/Tunis")

MINIO = boto3.client("s3", endpoint_url="http://minio:9000",
                      aws_access_key_id="admin", aws_secret_access_key="password123")

SOURCES_DIR = "/opt/airflow/sources"

today = date.today()
prefix = f"{today.year}/{today.month:02d}/{today.day:02d}"

def ingest_mockoon():
    for t in ["orders", "order_items", "customers"]:
        data = requests.get(f"http://mockoon:3000/{t}").content
        MINIO.put_object(Bucket="bronze", Key=f"mockoon/{t}/{prefix}/{t}.json", Body=data)

def ingest_sftp():
    ssh = paramiko.Transport(("sftp", 22))
    ssh.connect(username="dataops", password="dataops")
    sftp = paramiko.SFTPClient.from_transport(ssh)
    for f in sftp.listdir("/upload"):
        buf = io.BytesIO()
        sftp.getfo(f"/upload/{f}", buf)
        MINIO.put_object(Bucket="bronze", Key=f"sftp/{prefix}/{f}", Body=buf.getvalue())
    sftp.close()
    ssh.close()

"""def ingest_smb():
    conn = SMBConnection("dataops", "dataops", "airflow", "smb", use_ntlm_v2=True, is_direct_tcp=True)
    conn.connect("smb", 445, timeout=10)
    for f in conn.listPath("share", "/"):
        if f.isDirectory:
            continue
        buf = io.BytesIO()
        conn.retrieveFile("share", f"/{f.filename}", buf)
        MINIO.put_object(Bucket="bronze", Key=f"smb/{f.filename}", Body=buf.getvalue())
    conn.close()
"""

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

        MINIO.put_object(Bucket="bronze", Key=f"smb/{prefix}/{filename}", Body=data)

def ingest_csv():
    path = f"{SOURCES_DIR}/csv/olist_geolocation_dataset.csv"
    with open(path, "rb") as f:
        MINIO.put_object(Bucket="bronze", Key=f"csv/{prefix}/geolocation.csv", Body=f.read())


with DAG(
    dag_id="bronze_ingestion",
    start_date=pendulum.datetime(2026, 8, 11, tz=local_tz),
    schedule="15 13 * * *",
    catchup=False,
    is_paused_upon_creation=False,
    tags=["bronze", "ingestion"],
) as dag:
    PythonOperator(task_id="ingest_mockoon", python_callable=ingest_mockoon)
    PythonOperator(task_id="ingest_sftp", python_callable=ingest_sftp)
    PythonOperator(task_id="ingest_smb", python_callable=ingest_smb)
    PythonOperator(task_id="ingest_csv", python_callable=ingest_csv)
