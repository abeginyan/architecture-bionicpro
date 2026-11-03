"""ClickHouse access for the Reports API.

Only a single pre-aggregated, keyed SELECT against the mart — no joins or heavy
aggregation at request time. All user input is passed as bound query parameters
(never string-concatenated) to avoid SQL injection.
"""
from typing import Any, Iterator

import clickhouse_connect
from clickhouse_connect.driver.client import Client
from fastapi import Depends

from .config import Settings, get_settings

# ReplacingMergeTree(_loaded_at) -> FINAL collapses any not-yet-merged duplicates.
_REPORT_QUERY = """
SELECT user_email, customer_id, name, region, prosthesis_id, model, report_date,
       events_count, avg_response_ms, max_response_ms, p95_response_ms,
       errors_count, avg_battery_pct, movements_count, first_event_ts, last_event_ts
FROM marts.user_prosthesis_report FINAL
WHERE user_email = {email:String}
  AND (({dfrom:String} = '') OR report_date >= toDateOrNull({dfrom:String}))
  AND (({dto:String} = '') OR report_date <= toDateOrNull({dto:String}))
ORDER BY prosthesis_id, report_date
"""


def get_ch_client(settings: Settings = Depends(get_settings)) -> Iterator[Client]:
    """FastAPI dependency yielding a ClickHouse client. Overridden in tests."""
    client = clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_database,
    )
    try:
        yield client
    finally:
        client.close()


def query_report(
    client: Client,
    email: str,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Return the pre-computed mart rows for exactly one user (by email)."""
    result = client.query(
        _REPORT_QUERY,
        parameters={"email": email, "dfrom": date_from or "", "dto": date_to or ""},
    )
    columns = result.column_names
    return [dict(zip(columns, row)) for row in result.result_rows]
