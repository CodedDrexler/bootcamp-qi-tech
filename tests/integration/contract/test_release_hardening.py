"""Regressions for financial cases found while comparing the release."""
from concurrent.futures import ThreadPoolExecutor
from os import environ
from time import monotonic, sleep
from uuid import uuid4

import psycopg2
import pytest

from tests.utils import ObjectGenerator, PayloadGenerator, RequestGenerator


def test_funding_uuid_case_cannot_credit_twice():
    client, account = ObjectGenerator.create_client_with_account()
    payload = PayloadGenerator.create_deposit_payload(amount=1000)
    payload["funding_reference"] = str(uuid4()).lower()
    assert RequestGenerator.POST_transaction(account["account_key"], payload, client["client_key"])[0] == 201
    duplicate = {**payload, "request_control_key": str(uuid4()), "funding_reference": payload["funding_reference"].upper()}
    status, error = RequestGenerator.POST_transaction(account["account_key"], duplicate, client["client_key"])
    assert status == 409
    assert error["code"] == "QIT004006"
    assert RequestGenerator.GET_account(account["account_key"], client["client_key"])[1]["balance"] == 1000


def test_request_uuid_case_replays_original_operation():
    client, account = ObjectGenerator.create_client_with_account()
    payload = PayloadGenerator.create_deposit_payload(amount=1000)
    first = RequestGenerator.POST_transaction(account["account_key"], payload, client["client_key"])
    second = RequestGenerator.POST_transaction(account["account_key"], {
        **payload, "request_control_key": payload["request_control_key"].upper(),
        "funding_reference": payload["funding_reference"].upper()}, client["client_key"])
    assert first[0] == second[0] == 201
    assert first[1] == second[1]


@pytest.mark.parametrize("amount", [1.0, 100.0, True])
def test_money_requires_strict_json_integer(amount):
    client, account = ObjectGenerator.create_client_with_account()
    status, _ = RequestGenerator.POST_transaction(account["account_key"],
        PayloadGenerator.create_deposit_payload(amount=amount), client["client_key"])
    assert status == 400


def database_connection():
    url = environ.get("DATABASE_URL", "postgresql://bootcamp:bootcamp@localhost:5432/bootcamp")
    return psycopg2.connect(url.replace("postgresql+psycopg2://", "postgresql://"))


def wait_for_lock(observer, count):
    deadline = monotonic() + 3
    while monotonic() < deadline:
        with observer.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock'")
            if cursor.fetchone()[0] >= count:
                return
        sleep(.02)
    raise AssertionError("Concurrent requests did not reach the database barrier")


def test_account_cannot_close_while_deposit_is_committing():
    # SQL supplies only a barrier. All state and money originate through HTTP.
    client, account = ObjectGenerator.create_client_with_account()
    lock, observer = database_connection(), database_connection()
    observer.autocommit = True
    try:
        with lock.cursor() as cursor:
            cursor.execute("SELECT id FROM account WHERE account_key=%s FOR UPDATE", (account["account_key"],))
        with ThreadPoolExecutor(max_workers=2) as executor:
            deposit = executor.submit(RequestGenerator.POST_transaction, account["account_key"],
                PayloadGenerator.create_deposit_payload(amount=1000), client["client_key"])
            wait_for_lock(observer, 1)
            close = executor.submit(RequestGenerator.PUT_account_status, account["account_key"], "closed")
            try:
                wait_for_lock(observer, 2)
            finally:
                lock.rollback()
            assert deposit.result(timeout=10)[0] == 201
            assert close.result(timeout=10)[0] == 409
        state = RequestGenerator.GET_account(account["account_key"], client["client_key"])[1]
        assert state["status"] == "active" and state["balance"] == 1000
    finally:
        lock.rollback()
        lock.close()
        observer.close()
