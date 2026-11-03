-- ClickHouse DDL for the BionicPRO reports mart.
-- Executed by the Airflow DAG task `create_schema` (statements split on `;`).
-- All statements are idempotent (CREATE ... IF NOT EXISTS).

CREATE DATABASE IF NOT EXISTS staging;

CREATE DATABASE IF NOT EXISTS marts;

-- --- Staging: CRM dimensions (small, full reload each run) ------------------
CREATE TABLE IF NOT EXISTS staging.crm_customers
(
    customer_id UInt64,
    name        String,
    email       String,
    region      String
)
ENGINE = ReplacingMergeTree
ORDER BY customer_id;

CREATE TABLE IF NOT EXISTS staging.crm_prostheses
(
    prosthesis_id UInt64,
    customer_id   UInt64,
    model         String
)
ENGINE = ReplacingMergeTree
ORDER BY (customer_id, prosthesis_id);

-- --- Staging: telemetry facts (day partitions for drop-and-reload idempotency)
CREATE TABLE IF NOT EXISTS staging.telemetry_events
(
    prosthesis_id UInt64,
    ts            DateTime,
    response_ms   UInt32,
    latency_ms    UInt32,
    battery_pct   UInt8,
    movement_type LowCardinality(String),
    error_flag    UInt8
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ts)
ORDER BY (prosthesis_id, ts);

-- --- Mart: one row per (user_email, prosthesis_id, report_date) -------------
-- Keyed by user_email so the Reports API looks a pilot up directly by the
-- `email` claim from their JWT. Pre-aggregated => the API does a plain SELECT.
CREATE TABLE IF NOT EXISTS marts.user_prosthesis_report
(
    user_email      String,
    customer_id     UInt64,
    name            String,
    region          String,
    prosthesis_id   UInt64,
    model           String,
    report_date     Date,
    events_count    UInt64,
    avg_response_ms Float64,
    max_response_ms UInt32,
    p95_response_ms Float64,
    errors_count    UInt64,
    avg_battery_pct Float64,
    movements_count UInt64,
    first_event_ts  DateTime,
    last_event_ts   DateTime,
    _loaded_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_loaded_at)
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_email, prosthesis_id, report_date);
