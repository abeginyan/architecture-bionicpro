-- Telemetry schema (PostgreSQL) — "the existing database" from the architecture.
-- One row per prosthesis per emitted event.

CREATE TABLE IF NOT EXISTS telemetry_events (
    event_id      BIGSERIAL PRIMARY KEY,
    prosthesis_id BIGINT      NOT NULL,
    ts            TIMESTAMPTZ NOT NULL,
    response_ms   INTEGER     NOT NULL,   -- signal/response time in ms
    latency_ms    INTEGER     NOT NULL,   -- network latency in ms
    battery_pct   SMALLINT    NOT NULL,   -- 0..100
    movement_type TEXT        NOT NULL,   -- grip | release | rotate | walk | idle
    error_flag    SMALLINT    NOT NULL DEFAULT 0  -- 1 if the event reported an error
);

CREATE INDEX IF NOT EXISTS idx_telemetry_prosthesis_ts
    ON telemetry_events (prosthesis_id, ts);
