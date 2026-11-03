"""BionicPRO Reports API.

GET /health  — liveness, no auth.
GET /reports — the pre-computed report for the CURRENT authenticated user only.
               Identity is taken from the JWT; a client cannot request another
               user's data.
"""
import csv
import io
from datetime import date, datetime, timezone
from typing import Any

from clickhouse_connect.driver.client import Client
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from .clickhouse import get_ch_client, query_report
from .config import Settings, get_settings
from .schemas import ReportResponse, ReportRow, ReportSummary
from .security import CurrentUser, require_prothetic_user

settings = get_settings()

app = FastAPI(
    title="BionicPRO Reports API",
    description="Serves pre-computed per-pilot prosthesis reports from ClickHouse.",
    version="1.0.0",
)

# CORS: only the frontend origin may call the API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["GET"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=False,
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """Uniform, structured error body."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"status": exc.status_code, "message": exc.detail}},
        headers=getattr(exc, "headers", None),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _parse_date(value: str | None, field: str) -> str | None:
    if value is None or value == "":
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date for '{field}', expected YYYY-MM-DD",
        )
    return value


def _build_summary(rows: list[dict[str, Any]]) -> ReportSummary:
    total_events = sum(int(r["events_count"]) for r in rows)
    total_errors = sum(int(r["errors_count"]) for r in rows)
    # Event-weighted average response time across the returned rows.
    weighted = sum(float(r["avg_response_ms"]) * int(r["events_count"]) for r in rows)
    avg_response = round(weighted / total_events, 2) if total_events else 0.0
    return ReportSummary(
        prostheses=len({r["prosthesis_id"] for r in rows}),
        days=len({r["report_date"] for r in rows}),
        total_events=total_events,
        total_errors=total_errors,
        avg_response_ms=avg_response,
    )


def _to_csv(rows: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    fields = list(ReportRow.model_fields.keys())
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k) for k in fields})
    return buffer.getvalue()


@app.get("/reports")
def get_reports(
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    fmt: str = Query("json", alias="format", pattern="^(json|csv)$"),
    user_id: str | None = Query(None, description="Optional; must equal the token identity"),
    email_param: str | None = Query(None, alias="email"),
    user: CurrentUser = Depends(require_prothetic_user),
    client: Client = Depends(get_ch_client),
) -> Any:
    # Identity comes ONLY from the token. A client-supplied user_id/email that
    # differs from the token identity is rejected (never used to override it).
    for supplied in (user_id, email_param):
        if supplied is not None and supplied != user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Requested identity does not match the authenticated user",
            )

    date_from = _parse_date(date_from, "from")
    date_to = _parse_date(date_to, "to")

    rows = query_report(client, email=user.email, date_from=date_from, date_to=date_to)

    if fmt == "csv":
        return Response(
            content=_to_csv(rows),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="report.csv"'},
        )

    first = rows[0] if rows else {}
    return ReportResponse(
        user_email=user.email,
        username=user.username,
        customer_id=first.get("customer_id"),
        name=first.get("name"),
        region=first.get("region"),
        generated_at=datetime.now(timezone.utc),
        rows=[ReportRow(**r) for r in rows],
        summary=_build_summary(rows),
    )
