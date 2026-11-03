"""Test fixtures: a local RSA keypair to sign tokens (no network to Keycloak),
and a fake ClickHouse client (no OLAP needed)."""
import time
from datetime import date, datetime, timezone
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.clickhouse import get_ch_client
from app.config import get_settings
from app.main import app
from app.security import get_jwk_client

settings = get_settings()

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()

MART_COLUMNS = [
    "user_email", "customer_id", "name", "region", "prosthesis_id", "model",
    "report_date", "events_count", "avg_response_ms", "max_response_ms",
    "p95_response_ms", "errors_count", "avg_battery_pct", "movements_count",
    "first_event_ts", "last_event_ts",
]


def make_token(
    email="prothetic1@example.com",
    roles=("prothetic_user",),
    username="prothetic1",
    audience=None,
    issuer=None,
    exp_offset=3600,
    include_email=True,
):
    now = int(time.time())
    payload = {
        "iss": issuer or settings.keycloak_issuer,
        "aud": audience or settings.reports_api_audience,
        "iat": now,
        "exp": now + exp_offset,
        "preferred_username": username,
        "realm_access": {"roles": list(roles)},
    }
    if include_email:
        payload["email"] = email
    return jwt.encode(payload, _PRIVATE_KEY, algorithm="RS256")


def _row(email="prothetic1@example.com", customer_id=1, name="Prothetic One",
         region="Moscow", prosthesis_id=101, model="BionicArm X1", events=96,
         errors=3, avg_resp=85.5):
    ts0 = datetime(2026, 11, 1, 6, 0, tzinfo=timezone.utc)
    ts1 = datetime(2026, 11, 1, 23, 45, tzinfo=timezone.utc)
    return (
        email, customer_id, name, region, prosthesis_id, model,
        date(2026, 11, 1), events, avg_resp, 450, 180.0, errors, 72.5, 40, ts0, ts1,
    )


class FakeClickHouseClient:
    """Captures query parameters and returns canned mart rows."""

    def __init__(self, rows=None):
        self.rows = rows if rows is not None else [_row()]
        self.captured_parameters = None

    def query(self, query, parameters=None):
        self.captured_parameters = parameters
        return SimpleNamespace(column_names=MART_COLUMNS, result_rows=self.rows)

    def close(self):
        pass


@pytest.fixture
def jwk_override():
    """Make the app verify signatures with the test public key."""
    fake = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=_PUBLIC_KEY)
    )
    app.dependency_overrides[get_jwk_client] = lambda: fake
    yield
    app.dependency_overrides.pop(get_jwk_client, None)


@pytest.fixture
def fake_ch():
    client = FakeClickHouseClient()
    app.dependency_overrides[get_ch_client] = lambda: client
    yield client
    app.dependency_overrides.pop(get_ch_client, None)


@pytest.fixture
def client(jwk_override, fake_ch):
    return TestClient(app)
