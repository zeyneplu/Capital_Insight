from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select, func

from services.mock_bank.app.config import Settings
from services.mock_bank.app.main import create_app
from services.mock_bank.app.models import Account, Transaction, Posting
from services.mock_bank.app.security import issue_token


@pytest.fixture
def ledger(tmp_path, request):
    bank = getattr(request,"param","pnc")
    app = create_app(Settings(_env_file=None, bank_id=bank, database_url=f"sqlite:///{tmp_path / 'ledger.db'}"))
    with TestClient(app) as client:
        token = issue_token(app.state.secret,bank,f"{bank}-customer-001",1800)
        headers = {"Authorization":"Bearer "+token}
        yield client, headers, f"{bank}-customer-001"


def balance(ledger, kind):
    client,headers,prefix = ledger
    return Decimal(client.get(f"/v1/accounts/{prefix}-{kind}",headers=headers).json()["balance"])


def post(ledger, operation, kind="checking", amount="10.00", **extra):
    client,headers,prefix = ledger
    return client.post(f"/v1/accounts/{prefix}-{kind}/transactions",headers=headers,
        json={"request_id":str(uuid4()),"operation":operation,"amount":amount,**extra})


def assert_reconciled(ledger):
    client,_,_ = ledger
    with client.app.state.session_factory() as session:
        for account in session.scalars(select(Account)):
            rows = session.scalars(select(Transaction).where(Transaction.account_id==account.id)).all()
            delta = sum(row.amount if row.direction=="credit" else -row.amount for row in rows)
            if account.account_type in {"credit_card","personal_loan","auto_loan","mortgage"}:
                delta = -delta
            assert account.opening_balance + delta == account.balance


@pytest.mark.parametrize("operation,sign,category",[
    ("deposit",1,"transfers"),("salary",1,"salary"),("withdrawal",-1,"transfers"),
    ("purchase",-1,"other"),("payment",-1,"other"),("refund",1,"other"),
    ("interest",1,"other"),("fee",-1,"other"),
])
def test_cash_actions_have_correct_ledger_effect(ledger,operation,sign,category):
    before = balance(ledger,"checking")
    response = post(ledger,operation)
    assert response.status_code == 201,response.text
    assert response.json()["simulated"] is True
    assert response.json()["transactions"][0]["category"] == category
    assert balance(ledger,"checking") == before + Decimal("10.00")*sign
    assert_reconciled(ledger)


def test_transfer_is_atomic_and_replayed_only_once(ledger):
    client,headers,prefix = ledger
    before = [balance(ledger,kind) for kind in ("checking","savings")]
    body={"request_id":str(uuid4()),"operation":"transfer","amount":"123.45","counterparty_account_id":prefix+"-savings"}
    first=client.post(f"/v1/accounts/{prefix}-checking/transactions",headers=headers,json=body)
    assert first.status_code == 201,first.text
    again=client.post(f"/v1/accounts/{prefix}-checking/transactions",headers=headers,json=body)
    assert again.status_code == 201 and again.json()["replayed"] is True
    assert first.json()["posting_id"] == again.json()["posting_id"]
    assert len(first.json()["transactions"]) == 2
    assert balance(ledger,"checking") == before[0]-Decimal("123.45")
    assert balance(ledger,"savings") == before[1]+Decimal("123.45")
    body["amount"]="123.46"
    assert client.post(f"/v1/accounts/{prefix}-checking/transactions",headers=headers,json=body).status_code == 409
    assert_reconciled(ledger)


def test_posting_idempotency_survives_service_restart(ledger):
    client,headers,prefix=ledger
    before=balance(ledger,"checking")
    body={"request_id":str(uuid4()),"operation":"deposit","amount":"12.34"}
    path=f"/v1/accounts/{prefix}-checking/transactions"
    first=client.post(path,headers=headers,json=body)
    assert first.status_code==201
    with TestClient(create_app(client.app.state.settings)) as restarted:
        replay=restarted.post(path,headers=headers,json=body)
        assert replay.status_code==201 and replay.json()["replayed"] is True
        assert replay.json()["posting_id"]==first.json()["posting_id"]
        current=restarted.get(f"/v1/accounts/{prefix}-checking",headers=headers).json()
        assert Decimal(current["balance"])==before+Decimal("12.34")


@pytest.mark.parametrize("ledger",["chase"],indirect=True)
def test_card_purchase_payment_refund_and_credit_limit(ledger):
    _,_,prefix=ledger
    cash,owed=balance(ledger,"checking"),balance(ledger,"credit_card")
    assert post(ledger,"purchase","credit_card").status_code == 201
    assert balance(ledger,"credit_card")==owed+Decimal("10")
    assert post(ledger,"card_payment","credit_card",counterparty_account_id=prefix+"-checking").status_code == 201
    assert balance(ledger,"checking")==cash-Decimal("10")
    assert balance(ledger,"credit_card")==owed
    assert post(ledger,"refund","credit_card").status_code == 201
    assert balance(ledger,"credit_card")==owed-Decimal("10")
    before=balance(ledger,"credit_card")
    assert post(ledger,"purchase","credit_card",amount="1000000").status_code == 409
    assert balance(ledger,"credit_card")==before
    assert_reconciled(ledger)


def test_loan_payment_reduces_both_cash_and_outstanding_principal(ledger):
    client,headers,prefix=ledger
    cash,owed=balance(ledger,"checking"),balance(ledger,"auto_loan")
    result=post(ledger,"loan_payment","auto_loan",amount="100.00",counterparty_account_id=prefix+"-checking")
    assert result.status_code == 201,result.text
    assert balance(ledger,"checking")==cash-Decimal("100")
    loan=client.get(f"/v1/accounts/{prefix}-auto_loan",headers=headers).json()
    assert Decimal(loan["balance"])==Decimal(loan["outstanding_principal"])==owed-Decimal("100")
    assert_reconciled(ledger)


def test_failed_transfer_or_unauthorized_account_has_no_partial_posting(ledger):
    client,headers,prefix=ledger
    before=[balance(ledger,kind) for kind in ("checking","savings")]
    assert post(ledger,"transfer",amount="1000000",counterparty_account_id=prefix+"-savings").status_code == 409
    assert post(ledger,"transfer",counterparty_account_id="pnc-customer-002-savings").status_code == 404
    assert post(ledger,"transfer",counterparty_account_id=prefix+"-checking").status_code == 422
    assert client.post("/v1/accounts/pnc-customer-002-checking/transactions",headers=headers,
        json={"request_id":str(uuid4()),"operation":"deposit","amount":"10"}).status_code == 404
    assert before==[balance(ledger,kind) for kind in ("checking","savings")]
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Posting))==0


@pytest.mark.parametrize("amount",["0","-1","0.001","NaN","Infinity","1000001"])
def test_invalid_money_is_rejected(ledger,amount):
    assert post(ledger,"deposit",amount=amount).status_code == 422


def test_account_product_rules_are_enforced(ledger):
    assert post(ledger,"salary","auto_loan").status_code == 422
    assert post(ledger,"purchase","cd").status_code == 422
    assert post(ledger,"loan_payment","checking").status_code == 422
    assert post(ledger,"purchase",category="salary").status_code == 422


def test_postings_require_institution_authorization(ledger):
    client,_,prefix=ledger
    result=client.post(f"/v1/accounts/{prefix}-checking/transactions",
        json={"request_id":str(uuid4()),"operation":"deposit","amount":"10.00"})
    assert result.status_code==401


def test_simultaneous_debits_cannot_overdraw(ledger):
    client,_,prefix=ledger
    with client.app.state.session_factory() as session:
        account=session.get(Account,prefix+"-checking")
        account.balance=Decimal("100")
        session.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda _:post(ledger,"withdrawal",amount="75"),range(2)))
    assert sorted(response.status_code for response in responses)==[201,409]
    assert balance(ledger,"checking")==Decimal("25")
