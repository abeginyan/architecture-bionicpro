# Custom Airflow image: bakes the ETL dependencies (clickhouse-connect, psycopg2,
# pandas, pyarrow) so they are installed once at build time, not on every start.
FROM apache/airflow:2.9.3-python3.11

COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
