"""Access-control and behavior tests for the Reports API."""
from conftest import make_token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_health_requires_no_auth(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_no_token_returns_401(client):
    resp = client.get("/reports")
    assert resp.status_code == 401


def test_invalid_token_returns_401(client):
    resp = client.get("/reports", headers=_auth("not-a-real-jwt"))
    assert resp.status_code == 401


def test_expired_token_returns_401(client):
    token = make_token(exp_offset=-3600)
    resp = client.get("/reports", headers=_auth(token))
    assert resp.status_code == 401


def test_wrong_audience_returns_401(client):
    token = make_token(audience="some-other-api")
    resp = client.get("/reports", headers=_auth(token))
    assert resp.status_code == 401


def test_wrong_role_returns_403(client):
    token = make_token(roles=("user",))
    resp = client.get("/reports", headers=_auth(token))
    assert resp.status_code == 403


def test_happy_path_returns_own_rows(client, fake_ch):
    token = make_token(email="prothetic1@example.com")
    resp = client.get("/reports", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_email"] == "prothetic1@example.com"
    assert len(body["rows"]) == 1
    assert body["summary"]["total_events"] == 96
    # The mart is queried with EXACTLY the token identity, nothing else.
    assert fake_ch.captured_parameters["email"] == "prothetic1@example.com"


def test_query_is_always_filtered_by_token_identity(client, fake_ch):
    # Even if the DB held other users' rows, the WHERE is bound to the token.
    token = make_token(email="prothetic2@example.com", username="prothetic2")
    client.get("/reports", headers=_auth(token))
    assert fake_ch.captured_parameters["email"] == "prothetic2@example.com"


def test_user_id_param_mismatch_returns_403(client):
    token = make_token(email="prothetic1@example.com")
    resp = client.get(
        "/reports",
        params={"user_id": "prothetic2@example.com"},
        headers=_auth(token),
    )
    assert resp.status_code == 403


def test_email_param_mismatch_returns_403(client):
    token = make_token(email="prothetic1@example.com")
    resp = client.get(
        "/reports",
        params={"email": "prothetic2@example.com"},
        headers=_auth(token),
    )
    assert resp.status_code == 403


def test_matching_user_id_param_is_allowed(client):
    token = make_token(email="prothetic1@example.com")
    resp = client.get(
        "/reports",
        params={"user_id": "prothetic1@example.com"},
        headers=_auth(token),
    )
    assert resp.status_code == 200


def test_csv_format(client):
    token = make_token(email="prothetic1@example.com")
    resp = client.get("/reports", params={"format": "csv"}, headers=_auth(token))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    assert "prosthesis_id" in resp.text.splitlines()[0]


def test_invalid_date_returns_400(client):
    token = make_token(email="prothetic1@example.com")
    resp = client.get("/reports", params={"from": "11-01-2026"}, headers=_auth(token))
    assert resp.status_code == 400
