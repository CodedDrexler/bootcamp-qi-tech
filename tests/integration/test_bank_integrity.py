"""Additional database invariant checks, with scenarios created through the HTTP API."""

import os
from uuid import uuid4
import psycopg2
import pytest
from tests.integration.test_bank import account, balance, call, transaction


@pytest.fixture
def db():
    url = os.getenv(
        "DATABASE_URL", "postgresql://bootcamp:bootcamp@127.0.0.1:5432/bootcamp"
    )
    conn = psycopg2.connect(url.replace("postgresql+psycopg2://", "postgresql://"))
    yield conn
    conn.rollback()
    conn.close()


@pytest.mark.database
@pytest.mark.parametrize(
    "table", ["ledger_entry", "bank_transaction", "bank_status_event"]
)
def test_history_cannot_be_changed(db, table):
    a = account()
    transaction(a, 1000)
    with db.cursor() as cur:
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(f"DELETE FROM {table} WHERE id = (SELECT MAX(id) FROM {table})")
    db.rollback()
    assert balance(a) == 1000


@pytest.mark.database
def test_cached_balance_cannot_diverge_from_ledger(db):
    a = account()
    transaction(a, 1000)
    with db.cursor() as cur:
        cur.execute("UPDATE account SET balance = 999 WHERE account_key = %s", (a,))
    with pytest.raises(psycopg2.errors.CheckViolation):
        db.commit()
    db.rollback()
    assert balance(a) == 1000


@pytest.mark.database
def test_transaction_without_balanced_entries_cannot_commit(db):
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO bank_transaction (transaction_key,type,amount,fee) VALUES (%s,'DEPOSIT',100,0)",
            (str(uuid4()),),
        )
    with pytest.raises(psycopg2.errors.CheckViolation):
        db.commit()


@pytest.mark.database
def test_ledger_reconciles_after_transfer_and_reserve(db):
    a, b = account(), account()
    transaction(a, 2000)
    transaction(a, 500, "TRANSFER", destination_account_key=b)
    p = call(
        "POST",
        f"/accounts/{a}/piggy_banks",
        {"name": "Auditoria", "target_amount": 500},
    ).json()["piggy_bank_key"]
    call(
        "POST",
        f"/accounts/{a}/piggy_banks/{p}/transactions",
        {"type": "SAVE", "amount": 300},
    )
    with db.cursor() as cur:
        cur.execute(
            "SELECT transaction_id FROM ledger_entry GROUP BY transaction_id HAVING SUM(amount) <> 0"
        )
        assert cur.fetchall() == []
        cur.execute(
            "SELECT a.id FROM account a LEFT JOIN ledger_entry e ON e.account_id=a.id AND e.pocket='CHECKING' GROUP BY a.id HAVING a.balance <> COALESCE(SUM(e.amount),0)"
        )
        assert cur.fetchall() == []
        cur.execute(
            "SELECT p.id FROM piggy_bank p LEFT JOIN ledger_entry e ON e.piggy_bank_id=p.id GROUP BY p.id HAVING p.balance <> COALESCE(SUM(e.amount),0)"
        )
        assert cur.fetchall() == []


@pytest.mark.database
def test_lock_timeout_is_named_and_retry_does_not_duplicate(db):
    a = account()
    key = str(uuid4())
    path = f"/accounts/{a}/transactions"
    body = {"type": "DEPOSIT", "amount": 100}
    with db.cursor() as cur:
        cur.execute("SELECT id FROM account WHERE account_key = %s FOR UPDATE", (a,))
    response = call("POST", path, body, key)
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "QIT002008"
    assert response.headers.get("x-request-id")
    db.rollback()
    assert call("POST", path, body, key).status_code == 201
    assert balance(a) == 100
