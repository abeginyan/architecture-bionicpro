"""Pydantic response models for the Reports API."""
from datetime import date, datetime

from pydantic import BaseModel


class ReportRow(BaseModel):
    prosthesis_id: int
    model: str
    report_date: date
    events_count: int
    avg_response_ms: float
    max_response_ms: int
    p95_response_ms: float
    errors_count: int
    avg_battery_pct: float
    movements_count: int
    first_event_ts: datetime
    last_event_ts: datetime


class ReportSummary(BaseModel):
    prostheses: int
    days: int
    total_events: int
    total_errors: int
    avg_response_ms: float


class ReportResponse(BaseModel):
    user_email: str
    username: str | None = None
    customer_id: int | None = None
    name: str | None = None
    region: str | None = None
    generated_at: datetime
    rows: list[ReportRow]
    summary: ReportSummary
