import pytest

from tests.conftest import ALEX, JORDAN, auth, connect, latest_code


def test_full_flow_returns_only_my_accounts(client):
    token = connect(client, ALEX)
    accounts = client.get("/v1/accounts", headers=auth(token)).json()["accounts"]

    assert {a["type"] for a in accounts} == {"checking", "savings"}
    savings = next(a for a in accounts if a["type"] == "savings")
    assert savings["balance"] == "5000.00"  # exact decimal string, never a float
    assert savings["annual_rate"] == "0.0500"


def test_unknown_email_and_wrong_ssn_look_identical_to_a_match(client):
    ok = client.post("/v1/consents", json=ALEX)
    unknown = client.post("/v1/consents", json={"email": "who@example.com", "ssn_last4": "1234"})
    wrong_ssn = client.post("/v1/consents", json={**ALEX, "ssn_last4": "9999"})

    assert ok.status_code == unknown.status_code == wrong_ssn.status_code == 202
    assert ok.json()["message"] == unknown.json()["message"] == wrong_ssn.json()["message"]
    # ...but only the real match got an email.
    assert len(client.get("/dev/outbox", params={"email": ALEX["email"]}).json()) == 1


def test_wrong_ssn_consent_can_never_be_completed(client):
    consent = client.post("/v1/consents", json={**ALEX, "ssn_last4": "9999"}).json()
    resp = client.post(f"/v1/consents/{consent['consent_id']}/token", json={"code": "123456"})
    assert resp.status_code == 400


def test_code_is_single_use(client):
    consent = client.post("/v1/consents", json=ALEX).json()
    code = latest_code(client, ALEX["email"])
    url = f"/v1/consents/{consent['consent_id']}/token"
    assert client.post(url, json={"code": code}).status_code == 200
    assert client.post(url, json={"code": code}).status_code == 400


def test_attempts_are_limited(make_client):
    client = make_client(otp_max_attempts=3)
    consent = client.post("/v1/consents", json=ALEX).json()
    code = latest_code(client, ALEX["email"])
    wrong = "000000" if code != "000000" else "111111"
    url = f"/v1/consents/{consent['consent_id']}/token"

    for _ in range(3):
        assert client.post(url, json={"code": wrong}).status_code == 400
    # Locked out, even with the right code: brute force can't win.
    assert client.post(url, json={"code": code}).status_code == 429


def test_expired_code_is_rejected(make_client):
    client = make_client(otp_ttl_minutes=0)
    consent = client.post("/v1/consents", json=ALEX).json()
    code = latest_code(client, ALEX["email"])
    resp = client.post(f"/v1/consents/{consent['consent_id']}/token", json={"code": code})
    assert resp.status_code == 400


@pytest.mark.parametrize("header", [None, "Bearer not-a-real-token", "Basic abc"])
def test_accounts_require_a_valid_token(client, header):
    headers = {"Authorization": header} if header else {}
    assert client.get("/v1/accounts", headers=headers).status_code == 401


def test_cannot_read_someone_elses_transactions(client):
    alex_token, jordan_token = connect(client, ALEX), connect(client, JORDAN)
    alex_account = client.get("/v1/accounts", headers=auth(alex_token)).json()["accounts"][0]

    url = f"/v1/accounts/{alex_account['id']}/transactions"
    assert client.get(url, headers=auth(alex_token)).status_code == 200
    assert client.get(url, headers=auth(jordan_token)).status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"email": "not-an-email", "ssn_last4": "4821"},
        {"email": ALEX["email"], "ssn_last4": "0000"},
        {"email": ALEX["email"], "ssn_last4": "48a1"},
        {"email": ALEX["email"], "ssn_last4": "482"},
        {"email": ALEX["email"]},
    ],
)
def test_input_validation(client, body):
    assert client.post("/v1/consents", json=body).status_code == 422


def test_dev_outbox_is_hidden_outside_dev_mode(make_client):
    client = make_client(dev_mode=False, bank_secret="a-real-secret")
    assert client.get("/dev/outbox").status_code == 404


def test_refuses_to_run_in_prod_mode_with_default_secret(make_client):
    with pytest.raises(RuntimeError, match="BANK_SECRET"):
        make_client(dev_mode=False)
