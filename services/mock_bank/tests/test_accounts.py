from decimal import Decimal


def test_health_institution_docs(client):
    assert client.get("/health").json() == {"status": "ok", "bank_id": "chase"}
    assert client.get("/v1/institution").json()["id"] == "chase"
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 200
    assert "HTTPBearer" in client.get("/openapi.json").json()["components"]["securitySchemes"]


def test_accounts_ownership_balance(client, authorize):
    headers = authorize(client)
    accounts = client.get("/v1/accounts", headers=headers).json()
    assert len(accounts) >= 2
    for account in accounts:
        assert account["customer_id"] == "chase-customer-001"
        assert isinstance(account["balance"], str)
        assert Decimal(account["balance"]) >= 0
        response = client.get(f"/v1/accounts/{account['id']}/balance", headers=headers)
        assert response.json()["balance"] == account["balance"]
    for suffix in ("", "/balance", "/transactions"):
        assert client.get("/v1/accounts/chase-customer-002-checking"+suffix, headers=headers).status_code == 404
        assert client.get("/v1/accounts/nonexistent"+suffix, headers=headers).status_code == 404
    assert len(client.get("/v1/accounts?account_type=checking", headers=headers).json()) == 1
    assert client.get("/v1/accounts?account_type=invalid", headers=headers).status_code == 422
