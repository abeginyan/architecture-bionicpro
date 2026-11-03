"""BionicPRO reports ETL.

Pre-computes the per-pilot prosthesis report into ClickHouse so the Reports API
can serve it with a plain keyed SELECT (no heavy compute at request time).

Flow:
    create_schema -> [extract_crm, extract_telemetry] -> load_staging -> build_mart

Sources:  CRM DB (Postgres) + Telemetry DB (Postgres).
Sink:     ClickHouse (staging.* raw tables, marts.user_prosthesis_report).

Idempotent by design: staging tables are truncated and fully reloaded, and the
mart is truncated and rebuilt from staging on every run, so re-running a day
never duplicates rows.

Connection coordinates come from environment variables set in docker-compose
(CRM_DB_*, TELEMETRY_DB_*, CLICKHOUSE_*).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import clickhouse_connect
import pandas as pd
import psycopg2
from airflow.decorators import dag, task

DATA_DIR = Path("/opt/airflow/data")
DDL_PATH = Path("/opt/airflow/sql/clickhouse_ddl.sql")


def _clickhouse_client():
    """ClickHouse HTTP client (clickhouse-connect)."""
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
        username=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
    )


def _pg_connect(prefix: str):
    """Open a psycopg2 connection using <PREFIX>_DB_* env vars (CRM / TELEMETRY)."""
    return psycopg2.connect(
        host=os.environ[f"{prefix}_DB_HOST"],
        port=int(os.environ.get(f"{prefix}_DB_PORT", "5432")),
        dbname=os.environ[f"{prefix}_DB_NAME"],
        user=os.environ[f"{prefix}_DB_USER"],
        password=os.environ[f"{prefix}_DB_PASSWORD"],
    )


default_args = {
    "owner": "bionicpro",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}


@dag(
    dag_id="bionicpro_reports_etl",
    description="CRM + telemetry -> ClickHouse mart for the pilot reports API",
    schedule="0 2 * * *",           # daily at 02:00
    start_date=datetime(2024, 1, 1),
    catchup=False,
    is_paused_upon_creation=True,
    default_args=default_args,
    tags=["bionicpro", "reports", "etl"],
)
def bionicpro_reports_etl():

    @task
    def create_schema() -> None:
        """Create ClickHouse databases and tables (idempotent CREATE IF NOT EXISTS)."""
        ddl = DDL_PATH.read_text(encoding="utf-8")
        # Drop SQL line comments so splitting on ';' never yields a comment-only
        # (ClickHouse "Empty query") fragment.
        sql = "\n".join(
            line for line in ddl.splitlines() if not line.strip().startswith("--")
        )
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        client = _clickhouse_client()
        for stmt in statements:
            client.command(stmt)

    @task
    def extract_crm() -> dict:
        """Read customers and prostheses from the CRM DB into parquet."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = _pg_connect("CRM")
        try:
            customers = pd.read_sql(
                "SELECT customer_id, name, email, region FROM customers", conn
            )
            prostheses = pd.read_sql(
                "SELECT prosthesis_id, customer_id, model FROM prostheses", conn
            )
        finally:
            conn.close()

        customers_path = DATA_DIR / "crm_customers.parquet"
        prostheses_path = DATA_DIR / "crm_prostheses.parquet"
        customers.to_parquet(customers_path, index=False)
        prostheses.to_parquet(prostheses_path, index=False)
        return {"customers": str(customers_path), "prostheses": str(prostheses_path)}

    @task
    def extract_telemetry() -> str:
        """Read telemetry events from the Telemetry DB into parquet."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = _pg_connect("TELEMETRY")
        try:
            events = pd.read_sql(
                """
                SELECT prosthesis_id, ts, response_ms, latency_ms,
                       battery_pct, movement_type, error_flag
                FROM telemetry_events
                """,
                conn,
            )
        finally:
            conn.close()

        # ClickHouse DateTime is tz-naive; normalize to UTC then drop the tz.
        events["ts"] = pd.to_datetime(events["ts"], utc=True).dt.tz_localize(None)

        path = DATA_DIR / "telemetry_events.parquet"
        events.to_parquet(path, index=False)
        return str(path)

    @task
    def load_staging(crm: dict, telemetry_path: str) -> None:
        """Full reload of the ClickHouse staging tables (truncate + insert)."""
        customers = pd.read_parquet(crm["customers"])[["customer_id", "name", "email", "region"]]
        prostheses = pd.read_parquet(crm["prostheses"])[["prosthesis_id", "customer_id", "model"]]
        events = pd.read_parquet(telemetry_path)[
            ["prosthesis_id", "ts", "response_ms", "latency_ms",
             "battery_pct", "movement_type", "error_flag"]
        ]

        client = _clickhouse_client()
        client.command("TRUNCATE TABLE staging.crm_customers")
        client.command("TRUNCATE TABLE staging.crm_prostheses")
        client.command("TRUNCATE TABLE staging.telemetry_events")

        client.insert_df("staging.crm_customers", customers)
        client.insert_df("staging.crm_prostheses", prostheses)
        client.insert_df("staging.telemetry_events", events)

    @task
    def build_mart() -> int:
        """Rebuild the mart from staging (truncate + INSERT..SELECT). Returns row count."""
        client = _clickhouse_client()
        client.command("TRUNCATE TABLE marts.user_prosthesis_report")
        client.command(
            """
            INSERT INTO marts.user_prosthesis_report
                (user_email, customer_id, name, region, prosthesis_id, model, report_date,
                 events_count, avg_response_ms, max_response_ms, p95_response_ms,
                 errors_count, avg_battery_pct, movements_count, first_event_ts, last_event_ts)
            SELECT
                c.email                                AS user_email,
                c.customer_id                          AS customer_id,
                c.name                                 AS name,
                c.region                               AS region,
                p.prosthesis_id                        AS prosthesis_id,
                p.model                                AS model,
                toDate(t.ts)                           AS report_date,
                count()                                AS events_count,
                avg(t.response_ms)                     AS avg_response_ms,
                max(t.response_ms)                     AS max_response_ms,
                quantile(0.95)(t.response_ms)          AS p95_response_ms,
                sum(t.error_flag)                      AS errors_count,
                avg(t.battery_pct)                     AS avg_battery_pct,
                countIf(t.movement_type != 'idle')     AS movements_count,
                min(t.ts)                              AS first_event_ts,
                max(t.ts)                              AS last_event_ts
            FROM staging.telemetry_events AS t
            INNER JOIN staging.crm_prostheses AS p ON p.prosthesis_id = t.prosthesis_id
            INNER JOIN staging.crm_customers  AS c ON c.customer_id   = p.customer_id
            GROUP BY c.email, c.customer_id, c.name, c.region,
                     p.prosthesis_id, p.model, report_date
            """
        )
        result = client.query("SELECT count() FROM marts.user_prosthesis_report")
        row_count = int(result.result_rows[0][0])
        return row_count

    schema = create_schema()
    crm = extract_crm()
    telemetry = extract_telemetry()
    staged = load_staging(crm, telemetry)
    mart = build_mart()

    schema >> [crm, telemetry] >> staged >> mart


bionicpro_reports_etl()
