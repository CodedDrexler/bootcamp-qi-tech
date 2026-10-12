"""Contrato público: cenários preparados somente por HTTP, sem importar src/."""

from concurrent.futures import ThreadPoolExecutor
import os
from uuid import uuid4

import pytest
import requests

BASE = os.getenv("BANK_API_URL", "http://127.0.0.1:3000")
TOKEN = os.getenv("INTERNAL_TOKEN", "default_token")


def call(method, path, payload=None, key=None, token=TOKEN):
    headers = {"INTERNAL-TOKEN": token}
    if method == "POST":
        headers["Idempotency-Key"] = key or str(uuid4())
    return requests.request(
        method, BASE + path, json=payload, headers=headers, timeout=15
    )


def cpf():
    digits = [int(c) for c in f"{uuid4().int % 1000000000:09d}"]
    for size in (9, 10):
        v = sum(n * (size + 1 - i) for i, n in enumerate(digits)) * 10 % 11
        digits.append(0 if v == 10 else v)
    s = "".join(map(str, digits))
    return f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}"


def customer_payload():
    return {
        "name": "Cliente Teste",
        "email": f"{uuid4()}@example.test",
        "document_number": cpf(),
        "birthdate": "1990-05-17",
    }


def account():
    c = call("POST", "/customers", customer_payload())
    assert c.status_code == 201, c.text
    a = call("POST", "/accounts", {"customer_key": c.json()["customer_key"]})
    assert a.status_code == 201, a.text
    return a.json()["account_key"]


def transaction(a, amount, kind="DEPOSIT", **extra):
    return call(
        "POST", f"/accounts/{a}/transactions", {"type": kind, "amount": amount, **extra}
    )


def balance(a):
    r = call("GET", f"/accounts/{a}")
    assert r.status_code == 200, r.text
    return r.json()["balance"]


def test_customer_and_account_contract():
    data = customer_payload()
    key = str(uuid4())
    first = call("POST", "/customers", data, key)
    assert first.status_code == 201, first.text
    assert call("POST", "/customers", data, key).json() == first.json()
    assert call("POST", "/customers", {**data, "name": "Outra"}, key).status_code == 409
    assert call("POST", "/customers", data).status_code == 409
    c = first.json()["customer_key"]
    assert (
        call("GET", f"/customers/{c}").json()["document_number"]
        == data["document_number"]
    )
    a = call("POST", "/accounts", {"customer_key": c})
    assert a.status_code == 201
    assert call("POST", "/accounts", {"customer_key": c}).status_code == 409
    assert balance(a.json()["account_key"]) == 0


@pytest.mark.parametrize("amount", [0, -1, 1.0, 1.5, True, "100", 9000000000000001])
def test_invalid_money(amount):
    a = account()
    assert transaction(a, amount).status_code == 400
    assert balance(a) == 0


def test_validation_and_security():
    assert call("POST", "/customers", {}, token="wrong").status_code == 403
    assert call("POST", "/customers", {}).status_code == 400
    assert (
        call(
            "POST",
            "/customers",
            {**customer_payload(), "document_number": "111.111.111-11"},
        ).status_code
        == 422
    )
    assert (
        call(
            "POST", "/customers", {**customer_payload(), "birthdate": "2020-01-01"}
        ).status_code
        == 422
    )
    assert call("GET", f"/accounts/{uuid4()}").status_code == 404
    assert call("GET", "/accounts?limti=2").status_code == 400


def test_transfer_fee_statement_and_rollback():
    a, b = account(), account()
    assert transaction(a, 10000).status_code == 201
    r = transaction(a, 2500, "TRANSFER", destination_account_key=b)
    assert r.status_code == 201, r.text
    assert r.json()["fee"] == 100
    assert (balance(a), balance(b)) == (7400, 2500)
    assert (
        transaction(a, 7400, "TRANSFER", destination_account_key=b).status_code == 422
    )
    assert (balance(a), balance(b)) == (7400, 2500)
    assert transaction(a, 1, "TRANSFER", destination_account_key=a).status_code == 409
    page = call("GET", f"/accounts/{a}/transactions?limit=2&page=0").json()
    assert len(page["data"]) == 2 and page["is_last_page"] is False
    entries = (
        page["data"]
        + call("GET", f"/accounts/{a}/transactions?limit=2&page=1").json()["data"]
    )
    assert sum(e["amount"] for e in entries) == balance(a)
    assert any(e["type"] == "FEE" and e["amount"] == -100 for e in entries)


def test_piggy_bank_conserves_money_and_closes_empty_only():
    a = account()
    transaction(a, 5000)
    p = call(
        "POST", f"/accounts/{a}/piggy_banks", {"name": "Viagem", "target_amount": 4000}
    )
    assert p.status_code == 201, p.text
    pk = p.json()["piggy_bank_key"]
    route = f"/accounts/{a}/piggy_banks/{pk}"
    assert (
        call(
            "POST", route + "/transactions", {"type": "SAVE", "amount": 4000}
        ).status_code
        == 201
    )
    assert balance(a) == 1000
    assert call("GET", route).json()["balance"] == 4000
    assert call("PATCH", route, {"status": "CLOSED"}).status_code == 409
    assert (
        call(
            "POST", route + "/transactions", {"type": "REDEEM", "amount": 4001}
        ).status_code
        == 422
    )
    assert (
        call(
            "POST", route + "/transactions", {"type": "REDEEM", "amount": 4000}
        ).status_code
        == 201
    )
    assert balance(a) == 5000
    assert call("PATCH", route, {"status": "CLOSED"}).status_code == 200
    assert (
        call("POST", route + "/transactions", {"type": "SAVE", "amount": 1}).status_code
        == 409
    )
    other = account()
    assert call("GET", f"/accounts/{other}/piggy_banks/{pk}").status_code == 404


def test_concurrent_withdrawals_never_overdraw():
    a = account()
    transaction(a, 1000)
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(
            pool.map(lambda _: transaction(a, 400, "WITHDRAWAL"), range(8))
        )
    assert sorted(r.status_code for r in responses) == [201, 201] + [422] * 6
    assert balance(a) == 200


def test_concurrent_idempotency_executes_once():
    a = account()
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(
            pool.map(
                lambda _: call(
                    "POST",
                    f"/accounts/{a}/transactions",
                    {"type": "DEPOSIT", "amount": 1000},
                    key,
                ),
                range(8),
            )
        )
    assert all(r.status_code == 201 for r in responses)
    assert all(r.json() == responses[0].json() for r in responses)
    assert balance(a) == 1000


def test_account_closure_and_failed_key_can_retry():
    a = account()
    key = str(uuid4())
    path = f"/accounts/{a}/transactions"
    body = {"type": "WITHDRAWAL", "amount": 100}
    assert call("POST", path, body, key).status_code == 422
    transaction(a, 100)
    assert call("PATCH", f"/accounts/{a}", {"status": "CLOSED"}).status_code == 409
    assert call("POST", path, body, key).status_code == 201
    assert call("PATCH", f"/accounts/{a}", {"status": "CLOSED"}).status_code == 200
    assert transaction(a, 1).status_code == 409
    assert call("GET", path).status_code == 200


def test_cross_transfers_lock_in_the_same_order():
    a, b = account(), account()
    transaction(a, 3000)
    transaction(b, 3000)
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(
            pool.map(
                lambda i: transaction(
                    a if i % 2 else b,
                    50,
                    "TRANSFER",
                    destination_account_key=b if i % 2 else a,
                ),
                range(20),
            )
        )
    assert all(r.status_code == 201 for r in responses), [r.text for r in responses]
    assert (balance(a), balance(b)) == (2000, 2000)


def test_reserve_and_withdrawal_compete_for_the_same_balance():
    a = account()
    transaction(a, 1000)
    pk = call(
        "POST", f"/accounts/{a}/piggy_banks", {"name": "Reserva", "target_amount": 1000}
    ).json()["piggy_bank_key"]
    route = f"/accounts/{a}/piggy_banks/{pk}"
    with ThreadPoolExecutor(max_workers=2) as pool:
        save = pool.submit(
            call, "POST", route + "/transactions", {"type": "SAVE", "amount": 700}
        )
        withdraw = pool.submit(transaction, a, 700, "WITHDRAWAL")
        results = [save.result(), withdraw.result()]
    assert sorted(r.status_code for r in results) == [201, 422]
    assert balance(a) == 300
    assert call("GET", route).json()["balance"] in (0, 700)


def test_destination_closed_or_missing_does_not_debit_origin():
    a, b = account(), account()
    transaction(a, 1000)
    call("PATCH", f"/accounts/{b}", {"status": "CLOSED"})
    assert transaction(a, 100, "TRANSFER", destination_account_key=b).status_code == 409
    assert (
        transaction(
            a, 100, "TRANSFER", destination_account_key=str(uuid4())
        ).status_code
        == 404
    )
    assert balance(a) == 1000
    assert len(call("GET", f"/accounts/{a}/transactions").json()["data"]) == 1


def test_money_limit_rolls_back_destination_overflow():
    a, b = account(), account()
    transaction(a, 1000)
    transaction(b, 9000000000000000)
    assert transaction(a, 1, "TRANSFER", destination_account_key=b).status_code == 422
    assert transaction(b, 1).status_code == 422
    assert (balance(a), balance(b)) == (1000, 9000000000000000)


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=101", "page=-1", "limit=2&limit=3", "page=1.5", "token=secret"],
)
def test_pagination_rejects_invalid_query(query):
    assert call("GET", "/customers?" + query).status_code == 400


def test_post_requires_idempotency_key_and_unknown_fields_are_rejected():
    headers = {"INTERNAL-TOKEN": TOKEN}
    r = requests.post(
        BASE + "/customers", json=customer_payload(), headers=headers, timeout=10
    )
    assert r.status_code == 400
    assert (
        call("POST", "/customers", {**customer_payload(), "extra": "x"}).status_code
        == 400
    )
    assert call("POST", "/customers", customer_payload(), "bad key").status_code == 400
    a = account()
    assert transaction(a, 1, "TRANSFER").status_code == 400
    assert transaction(a, 1, destination_account_key=str(uuid4())).status_code == 400


def test_piggy_goal_is_informational_and_history_is_complete():
    a = account()
    transaction(a, 1000)
    data = {"name": "Meta", "target_amount": 300}
    pk = call("POST", f"/accounts/{a}/piggy_banks", data).json()["piggy_bank_key"]
    assert call("POST", f"/accounts/{a}/piggy_banks", data).status_code == 409
    route = f"/accounts/{a}/piggy_banks/{pk}"
    call("POST", route + "/transactions", {"type": "SAVE", "amount": 500})
    assert call("GET", route).json()["goal_reached"] is True
    call("POST", route + "/transactions", {"type": "REDEEM", "amount": 200})
    data = call("GET", route + "/transactions").json()["data"]
    assert sum(e["amount"] for e in data) == 300
    assert data[0]["balance_after"] == 300
    assert call("GET", f"/accounts/{a}").json()["total_balance"] == 1000
    assert (
        call("GET", f"/accounts/{a}/piggy_banks?limit=1").json()["data"][0][
            "piggy_bank_key"
        ]
        == pk
    )
    assert call("PATCH", f"/accounts/{a}", {"status": "CLOSED"}).status_code == 409


def test_closed_account_and_piggy_patch_repeat_without_duplicate_events():
    a = account()
    pk = call(
        "POST", f"/accounts/{a}/piggy_banks", {"name": "Vazio", "target_amount": 100}
    ).json()["piggy_bank_key"]
    route = f"/accounts/{a}/piggy_banks/{pk}"
    for _ in range(2):
        assert call("PATCH", route, {"status": "CLOSED"}).status_code == 200
        assert call("PATCH", f"/accounts/{a}", {"status": "CLOSED"}).status_code == 200
    assert len(call("GET", route).json()["status_events"]) == 2
    assert len(call("GET", f"/accounts/{a}").json()["status_events"]) == 2


def test_request_id_metrics_and_error_shape():
    r = requests.get(
        BASE + "/customers",
        headers={"INTERNAL-TOKEN": TOKEN, "X-Request-ID": "acceptance-123"},
        timeout=10,
    )
    assert r.headers["x-request-id"] == "acceptance-123"
    metrics = call("GET", "/metrics")
    assert metrics.status_code == 200
    assert "bank_http_requests_total" in metrics.text
    assert "/accounts/{account_key}/transactions" in metrics.text
    assert call("GET", "/metrics", token="").status_code == 403
    r = call("GET", f"/accounts/{uuid4()}")
    assert set(r.json()) == {"title", "description", "translation", "code"}
    assert r.json()["code"] == "QIT002001"
