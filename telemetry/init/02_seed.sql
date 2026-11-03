-- Telemetry demo data: one event every 15 minutes per prosthesis over the last
-- 7 days, for all 6 prostheses of the 3 demo customers. Values are randomized
-- but realistic. Guarded so a re-run on a non-empty table is a no-op.

INSERT INTO telemetry_events
    (prosthesis_id, ts, response_ms, latency_ms, battery_pct, movement_type, error_flag)
SELECT
    p.prosthesis_id,
    g.ts,
    -- response time: mostly 30-150ms, with occasional spikes for p95/max to bite
    (30 + floor(random() * 120) + (CASE WHEN random() < 0.05 THEN floor(random() * 400) ELSE 0 END))::int,
    (5 + floor(random() * 75))::int,
    -- battery: drains across the day, resets each morning (06:00)
    greatest(5, 100 - floor(extract(epoch FROM (g.ts - date_trunc('day', g.ts))) / 3600.0 * 4))::smallint,
    (ARRAY['grip', 'release', 'rotate', 'walk', 'idle'])[1 + floor(random() * 5)::int],
    (CASE WHEN random() < 0.03 THEN 1 ELSE 0 END)::smallint
FROM (VALUES (101), (102), (201), (202), (301), (302)) AS p(prosthesis_id)
CROSS JOIN generate_series(
    date_trunc('hour', now()) - interval '7 days',
    date_trunc('hour', now()),
    interval '15 minutes'
) AS g(ts)
WHERE NOT EXISTS (SELECT 1 FROM telemetry_events);
