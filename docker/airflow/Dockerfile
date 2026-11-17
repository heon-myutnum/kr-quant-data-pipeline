FROM apache/airflow:3.3.2-python3.12

COPY docker/airflow/requirements.txt /requirements.txt
COPY docker/airflow/pools.json /opt/airflow/pools.json
RUN pip install --no-cache-dir \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.3.2/constraints-3.12.txt" \
    -r /requirements.txt
