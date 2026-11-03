-- CRM schema (PostgreSQL) — stand-in for the Bitrix24 CRM database.
-- Runs once, on first init of an empty data volume (/docker-entrypoint-initdb.d).

CREATE TABLE IF NOT EXISTS customers (
    customer_id  BIGINT PRIMARY KEY,
    name         TEXT        NOT NULL,
    email        TEXT        NOT NULL UNIQUE,
    region       TEXT        NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS prostheses (
    prosthesis_id BIGINT PRIMARY KEY,
    customer_id   BIGINT      NOT NULL REFERENCES customers(customer_id),
    model         TEXT        NOT NULL,
    serial_number TEXT        NOT NULL,
    purchased_at  DATE        NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_prostheses_customer ON prostheses(customer_id);
