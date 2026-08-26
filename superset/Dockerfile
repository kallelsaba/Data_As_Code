FROM apache/superset:latest

COPY superset_config.py /app/pythonpath/superset_config.py

USER root

COPY requirements-local.txt /app/requirements-local.txt

RUN pip install --no-cache-dir \
    --target=/app/.venv/lib/python3.10/site-packages \
    -r /app/requirements-local.txt

USER superset
