def test_pagination_and_filters(client, authorize):
    headers = authorize(client)
    url = "/v1/accounts/chase-customer-001-checking/transactions"
    first = client.get(url+"?limit=2", headers=headers).json()
    second = client.get(url+"?limit=2&offset=2", headers=headers).json()
    assert first["total"] > 90
    assert len(first["items"]) == 2
    assert not {x["id"] for x in first["items"]} & {x["id"] for x in second["items"]}
    assert first["items"][0]["transaction_date"] >= second["items"][0]["transaction_date"]
    assert isinstance(first["items"][0]["amount"], str)
    salary = client.get(url+"?category=salary&start_date=2026-10-01&end_date=2026-11-01", headers=headers).json()
    assert salary["items"]
    assert all(x["category"] == "salary" and "2026-10-01" <= x["transaction_date"] <= "2026-11-01" for x in salary["items"])
    assert client.get(url+"?offset=9999", headers=headers).json()["items"] == []
    for query in ("limit=0", "limit=101", "offset=-1", "category=bad", "start_date=bad", "start_date=2026-11-01&end_date=2026-01-01"):
        assert client.get(url+"?"+query, headers=headers).status_code == 422
