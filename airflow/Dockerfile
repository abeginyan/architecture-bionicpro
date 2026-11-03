# Custom Airflow image: bakes the ETL dependencies (clickhouse-connect, psycopg2,
# pandas, pyarrow) so they are installed once at build time, not on every start.
FROM apache/airflow:2.9.3-python3.11

COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# Create the ETL scratch dir in the image so the named volume mounted there
# inherits the airflow user's ownership (fresh volumes copy the image dir's
# uid/gid). Without this it would be root-owned and tasks (uid 50000) can't write.
RUN mkdir -p /opt/airflow/data
