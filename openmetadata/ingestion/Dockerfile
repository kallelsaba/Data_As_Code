FROM python:3.11-slim
RUN pip install --no-cache-dir \
    "openmetadata-ingestion[trino,postgres,dbt,superset]==1.12.14" \
    cachetools
WORKDIR /ingestion
ENTRYPOINT ["tail", "-f", "/dev/null"]
