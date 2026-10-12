from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from os import environ
from uuid import uuid4

import pytest
import requests
from tests.utils import ObjectGenerator, PayloadGenerator, RequestGenerator


def call(method, path, client, body=None, params=None, token="default_token"):
    base = f"http://{environ.get('SERVER_LOCALHOST', '127.0.0.1')}:{environ.get('API_PORT', '3000')}"
    headers = {"INTERNAL-TOKEN": token}
    if client is not None:
        headers["X-CLIENT-KEY"] = client
    return requests.request(
        method, base + path, json=body, params=params, headers=headers, timeout=15
    )


def setup_bank(amount=10000):
    client, account = ObjectGenerator.create_client_with_account()
    if amount:
        ObjectGenerator.deposit(account["account_key"], client["client_key"], amount)
    return client["client_key"], account["account_key"]


def create(client, account, **extra):
    body = {
        "request_control_key": str(uuid4()),
        "name": "Viagem",
        "target_amount": 4000,
        **extra,
    }
    response = call("POST", f"/account/{account}/piggy_bank", client, body)
    assert response.status_code == 201, response.text
    return response.json()["piggy_bank_key"], body, response.json()


def path(account, piggy):
    return f"/account/{account}/piggy_bank/{piggy}"


def move(client, account, piggy, kind, amount, key=None):
    return call(
        "POST",
        path(account, piggy) + "/transaction",
        client,
        {"request_control_key": key or str(uuid4()), "type": kind, "amount": amount},
    )


def balances(client, account):
    response = call("GET", f"/account/{account}/balances", client)
    assert response.status_code == 200, response.text
    return response.json()


def test_create_goal_metadata_and_idempotent_replay():
    c, a = setup_bank()
    due = (date.today() + timedelta(days=90)).isoformat()
    p, body, response = create(c, a, description="Férias em família", target_date=due)
    assert call("POST", f"/account/{a}/piggy_bank", c, body).json() == response
    changed = call(
        "POST", f"/account/{a}/piggy_bank", c, {**body, "target_amount": 5000}
    )
    assert changed.status_code == 409
    data = call("GET", path(a, p), c).json()
    assert data["name"] == "Viagem" and data["balance"] == 0
    assert data["target_date"] == due and data["description"] == "Férias em família"
    assert data["version"] == 1 and data["progress_basis_points"] == 0
    assert data["currency"] == "BRL" and data["status"] == "active"
    assert "id" not in data


def test_reserve_and_redeem_conserve_money_and_reconstruct_both_statements():
    c, a = setup_bank()
    p, _, _ = create(c, a)
    reserve = move(c, a, p, "reserve", 4000)
    assert reserve.status_code == 201, reserve.text
    assert reserve.json()["fee_amount"] == 0
    assert reserve.json()["balance_after"] == 4000
    assert reserve.json()["available_balance_after"] == 6000
    assert balances(c, a) == {
        "account_key": a,
        "available_balance": 6000,
        "reserved_balance": 4000,
        "total_balance": 10000,
        "currency": "BRL",
    }
    assert move(c, a, p, "redeem", 1500).status_code == 201
    data = call("GET", path(a, p) + "/transactions", c).json()["data"]
    assert [e["balance_effect"] for e in data] == [-1500, 4000]
    assert data[0]["balance_after"] == 2500
    _, checking = RequestGenerator.GET_transactions(a, c)
    assert sum(e["balance_effect"] for e in checking["data"]) == 7500
    assert not any(e["type"] == "fee" for e in checking["data"])
    assert balances(c, a)["total_balance"] == 10000


def test_reserved_money_cannot_be_spent_and_goals_do_not_block_redemption():
    c, a = setup_bank(5000)
    other_c, other_a = setup_bank(0)
    p, _, _ = create(c, a, target_amount=1000)
    assert move(c, a, p, "reserve", 4500).status_code == 201
    data = call("GET", path(a, p), c).json()
    assert data["goal_reached"] is True and data["progress_basis_points"] == 10000
    status, _ = RequestGenerator.POST_transaction(
        a, PayloadGenerator.create_transfer_payload(other_a, amount=400), c
    )
    assert status == 422  # available 500 does not cover 400 + fee 200
    assert move(c, a, p, "redeem", 4500).status_code == 201
    assert balances(c, a)["available_balance"] == 5000
    assert RequestGenerator.GET_account(other_a, other_c)[1]["balance"] == 0


def test_metadata_edits_use_version_and_record_audit_events():
    c, a = setup_bank()
    p, _, _ = create(c, a)
    endpoint = path(a, p)
    result = call(
        "PATCH",
        endpoint,
        c,
        {"expected_version": 1, "name": "Entrada da casa", "target_amount": 20000},
    )
    assert result.status_code == 200, result.text
    assert result.json()["version"] == 2
    assert (
        call(
            "PATCH", endpoint, c, {"expected_version": 1, "name": "Sobrescrita"}
        ).status_code
        == 409
    )
    events = call("GET", endpoint + "/events", c).json()["data"]
    assert [e["type"] for e in events] == ["updated", "created"]
    assert events[0]["changes"]["name"] == {"from": "Viagem", "to": "Entrada da casa"}


def test_two_metadata_edits_with_same_version_accept_only_one():
    c, a = setup_bank()
    p, _, _ = create(c, a)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda name: call(
                    "PATCH", path(a, p), c, {"expected_version": 1, "name": name}
                ),
                ["Casa", "Carro"],
            )
        )
    assert sorted(r.status_code for r in results) == [200, 409]


def test_close_requires_empty_reserve_and_is_idempotent():
    c, a = setup_bank()
    p, body, creation = create(c, a)
    endpoint = path(a, p)
    move(c, a, p, "reserve", 10000)
    assert RequestGenerator.PUT_account_status(a, "closed")[0] == 409
    assert (
        call(
            "PUT", endpoint + "/status", c, {"expected_version": 1, "status": "closed"}
        ).status_code
        == 409
    )
    move(c, a, p, "redeem", 10000)
    r1 = call(
        "PUT", endpoint + "/status", c, {"expected_version": 1, "status": "closed"}
    )
    r2 = call(
        "PUT", endpoint + "/status", c, {"expected_version": 1, "status": "closed"}
    )
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()
    assert move(c, a, p, "reserve", 1).status_code == 423
    assert (
        call("PATCH", endpoint, c, {"expected_version": 2, "name": "Outra"}).status_code
        == 423
    )
    assert call("POST", f"/account/{a}/piggy_bank", c, body).json() == creation
    assert len(call("GET", endpoint + "/events", c).json()["data"]) == 2


def test_replay_storm_moves_money_once_and_survives_block():
    c, a = setup_bank()
    p, _, _ = create(c, a)
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _: move(c, a, p, "reserve", 5000, key), range(8))
        )
    assert all(r.status_code == 201 for r in results)
    assert all(r.json() == results[0].json() for r in results)
    assert balances(c, a)["reserved_balance"] == 5000
    RequestGenerator.PUT_account_status(a, "blocked")
    assert move(c, a, p, "reserve", 5000, key.upper()).json() == results[0].json()
    assert move(c, a, p, "redeem", 1).status_code == 423


def test_multiple_reserves_compete_for_available_balance():
    c, a = setup_bank(1000)
    p, _, _ = create(c, a)
    q, _, _ = create(c, a, name="Emergência")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda piggy: move(c, a, piggy, "reserve", 700), [p, q])
        )
    assert sorted(r.status_code for r in results) == [201, 422]
    assert balances(c, a)["available_balance"] == 300
    assert balances(c, a)["reserved_balance"] == 700


def test_creation_replay_storm_creates_one_piggy():
    c, a = setup_bank()
    body = {
        "request_control_key": str(uuid4()),
        "name": "Reserva",
        "target_amount": 1000,
    }
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(
            pool.map(
                lambda _: call("POST", f"/account/{a}/piggy_bank", c, body), range(6)
            )
        )
    assert all(r.status_code == 201 for r in results)
    assert all(r.json() == results[0].json() for r in results)
    assert len(call("GET", f"/account/{a}/piggy_banks", c).json()["data"]) == 1


def test_ownership_is_required_on_every_piggy_surface():
    c, a = setup_bank()
    p, _, _ = create(c, a)
    other_c, other_a = setup_bank()
    endpoints = [
        ("GET", path(a, p), None),
        ("GET", path(a, p) + "/events", None),
        ("GET", path(a, p) + "/transactions", None),
        ("GET", f"/account/{a}/piggy_banks", None),
        ("GET", f"/account/{a}/balances", None),
        ("PATCH", path(a, p), {"expected_version": 1, "name": "Outra"}),
        ("PUT", path(a, p) + "/status", {"expected_version": 1, "status": "closed"}),
        (
            "POST",
            path(a, p) + "/transaction",
            {"request_control_key": str(uuid4()), "type": "reserve", "amount": 1},
        ),
    ]
    for method, endpoint, body in endpoints:
        assert call(method, endpoint, None, body).status_code == 401
        assert call(method, endpoint, other_c, body).status_code == 404
        assert call(method, endpoint, c, body, token="wrong").status_code == 403
    assert call("GET", path(other_a, p), other_c).status_code == 404


@pytest.mark.parametrize("amount", [0, -1, 1.0, True, "100", 100000001])
def test_invalid_movement_never_changes_balances(amount):
    c, a = setup_bank()
    p, _, _ = create(c, a)
    assert move(c, a, p, "reserve", amount).status_code == 400
    assert balances(c, a)["available_balance"] == 10000
    assert balances(c, a)["reserved_balance"] == 0


def test_insufficient_reserve_and_global_financial_key_conflict():
    c, a = setup_bank()
    p, _, _ = create(c, a)
    assert move(c, a, p, "redeem", 1).status_code == 422
    key = str(uuid4())
    assert move(c, a, p, "reserve", 1000, key).status_code == 201
    assert move(c, a, p, "reserve", 1001, key).status_code == 409
    assert move(c, a, p, "redeem", 1000, key).status_code == 409
    assert (
        RequestGenerator.POST_transaction(
            a, PayloadGenerator.create_deposit_payload(request_control_key=key), c
        )[0]
        == 409
    )
    assert balances(c, a)["reserved_balance"] == 1000


def test_normalized_name_uniqueness_and_list_filter_pagination():
    c, a = setup_bank()
    p, _, _ = create(c, a, name=" Minha   Viagem ")
    body = {
        "request_control_key": str(uuid4()),
        "name": "MINHA VIAGEM",
        "target_amount": 1000,
    }
    assert call("POST", f"/account/{a}/piggy_bank", c, body).status_code == 409
    create(c, a, name="Casa")
    first = call(
        "GET", f"/account/{a}/piggy_banks", c, params={"limit": 1, "page": 0}
    ).json()
    assert first["is_last_page"] is False and first["data"][0]["name"] == "Casa"
    call("PUT", path(a, p) + "/status", c, {"expected_version": 1, "status": "closed"})
    assert (
        len(
            call(
                "GET", f"/account/{a}/piggy_banks", c, params={"status": "closed"}
            ).json()["data"]
        )
        == 1
    )
    assert (
        call("GET", f"/account/{a}/piggy_banks", c, params={"limit": 101}).status_code
        == 400
    )


def test_invalid_calendar_date_and_stale_version_have_named_errors():
    c, a = setup_bank()
    body = {
        "request_control_key": str(uuid4()),
        "name": "Meta",
        "target_amount": 1000,
        "target_date": "2027-02-30",
    }
    assert call("POST", f"/account/{a}/piggy_bank", c, body).status_code == 422
    p, _, _ = create(c, a)
    assert (
        call(
            "PATCH",
            path(a, p),
            c,
            {"expected_version": 1, "target_date": None, "description": None},
        ).status_code
        == 200
    )
    assert (
        call(
            "PATCH", path(a, p), c, {"expected_version": 1, "target_amount": 2000}
        ).status_code
        == 409
    )
