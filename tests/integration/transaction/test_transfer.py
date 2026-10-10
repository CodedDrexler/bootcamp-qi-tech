from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from tests.utils import DbUtils, ObjectGenerator, PayloadGenerator, RequestGenerator


class TestTransfer:
    def test_transfer_moves_money_and_charges_fee(self):
        origin_client, origin_account = ObjectGenerator.create_client_with_account()
        destination_client, destination_account = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin_account["account_key"], origin_client["client_key"], 50000)

        payload = PayloadGenerator.create_transfer_payload(destination_account["account_key"], amount=20000)
        status, response = RequestGenerator.POST_transaction(
            origin_account["account_key"], payload, origin_client["client_key"]
        )
        assert status == 201
        assert response["type"] == "transfer"
        assert response["amount"] == 20000
        assert response["fee_amount"] == 200
        assert response["origin_account_key"] == origin_account["account_key"]
        assert response["destination_account_key"] == destination_account["account_key"]

        status, origin = RequestGenerator.GET_account(
            origin_account["account_key"], origin_client["client_key"]
        )
        status, destination = RequestGenerator.GET_account(
            destination_account["account_key"], destination_client["client_key"]
        )
        assert origin["balance"] == 29800
        assert destination["balance"] == 20000

    def test_insufficient_balance_changes_nothing(self):
        origin_client, origin_account = ObjectGenerator.create_client_with_account()
        destination_client, destination_account = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin_account["account_key"], origin_client["client_key"], 10000)

        payload = PayloadGenerator.create_transfer_payload(destination_account["account_key"], amount=10000)
        status, response = RequestGenerator.POST_transaction(
            origin_account["account_key"], payload, origin_client["client_key"]
        )
        assert status == 422
        assert response["code"] == "QIT004001"

        _, origin = RequestGenerator.GET_account(origin_account["account_key"], origin_client["client_key"])
        _, destination = RequestGenerator.GET_account(
            destination_account["account_key"], destination_client["client_key"]
        )
        assert origin["balance"] == 10000
        assert destination["balance"] == 0

        _, statement = RequestGenerator.GET_transactions(
            origin_account["account_key"], origin_client["client_key"]
        )
        assert [item["type"] for item in statement["data"]] == ["deposit"]

    def test_exact_balance_including_fee_can_be_spent(self):
        origin_client, origin_account = ObjectGenerator.create_client_with_account()
        destination_client, destination_account = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin_account["account_key"], origin_client["client_key"], 10200)

        payload = PayloadGenerator.create_transfer_payload(destination_account["account_key"], amount=10000)
        status, _ = RequestGenerator.POST_transaction(
            origin_account["account_key"], payload, origin_client["client_key"]
        )
        assert status == 201

        _, origin = RequestGenerator.GET_account(origin_account["account_key"], origin_client["client_key"])
        _, destination = RequestGenerator.GET_account(
            destination_account["account_key"], destination_client["client_key"]
        )
        assert origin["balance"] == 0
        assert destination["balance"] == 10000

    def test_same_account_transfer_is_rejected(self):
        client, account = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(account["account_key"], client["client_key"], 10000)
        payload = PayloadGenerator.create_transfer_payload(account["account_key"], amount=1000)
        status, response = RequestGenerator.POST_transaction(
            account["account_key"], payload, client["client_key"]
        )
        assert status == 409
        assert response["code"] == "QIT004002"

    def test_unknown_destination_does_not_debit_origin(self):
        client, account = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(account["account_key"], client["client_key"], 10000)
        unknown = "00000000-0000-4000-8000-000000000000"
        payload = PayloadGenerator.create_transfer_payload(unknown, amount=1000)
        status, response = RequestGenerator.POST_transaction(
            account["account_key"], payload, client["client_key"]
        )
        assert status == 404
        assert response["code"] == "QIT003001"
        _, current = RequestGenerator.GET_account(account["account_key"], client["client_key"])
        assert current["balance"] == 10000

    def test_transfer_schema_requires_destination(self):
        client, account = ObjectGenerator.create_client_with_account()
        payload = {
            "request_control_key": str(uuid4()),
            "type": "transfer",
            "amount": 1000,
        }
        status, response = RequestGenerator.POST_transaction(
            account["account_key"], payload, client["client_key"]
        )
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_transfer_is_idempotent_and_fee_is_not_duplicated(self):
        origin_client, origin_account = ObjectGenerator.create_client_with_account()
        destination_client, destination_account = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin_account["account_key"], origin_client["client_key"], 50000)
        payload = PayloadGenerator.create_transfer_payload(destination_account["account_key"], amount=20000)

        status, first = RequestGenerator.POST_transaction(
            origin_account["account_key"], payload, origin_client["client_key"]
        )
        assert status == 201
        status, second = RequestGenerator.POST_transaction(
            origin_account["account_key"], payload, origin_client["client_key"]
        )
        assert status == 201
        assert first == second

        _, origin = RequestGenerator.GET_account(origin_account["account_key"], origin_client["client_key"])
        _, destination = RequestGenerator.GET_account(
            destination_account["account_key"], destination_client["client_key"]
        )
        assert origin["balance"] == 29800
        assert destination["balance"] == 20000

        _, statement = RequestGenerator.GET_transactions(
            origin_account["account_key"], origin_client["client_key"]
        )
        assert len([x for x in statement["data"] if x["type"] == "fee"]) == 1
        assert len([x for x in statement["data"] if x["type"] == "transfer"]) == 1

    def test_same_request_key_with_different_transfer_conflicts(self):
        origin_client, origin_account = ObjectGenerator.create_client_with_account()
        _, first_destination = ObjectGenerator.create_client_with_account()
        _, second_destination = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin_account["account_key"], origin_client["client_key"], 50000)
        key = str(uuid4())

        first = PayloadGenerator.create_transfer_payload(
            first_destination["account_key"], amount=1000, request_control_key=key
        )
        second = PayloadGenerator.create_transfer_payload(
            second_destination["account_key"], amount=1000, request_control_key=key
        )
        status, _ = RequestGenerator.POST_transaction(
            origin_account["account_key"], first, origin_client["client_key"]
        )
        assert status == 201
        status, response = RequestGenerator.POST_transaction(
            origin_account["account_key"], second, origin_client["client_key"]
        )
        assert status == 409
        assert response["code"] == "QIT004003"

    def test_two_concurrent_transfers_cannot_spend_same_balance(self):
        DbUtils.rollback()
        origin_client, origin_account = ObjectGenerator.create_client_with_account()
        _, destination_a = ObjectGenerator.create_client_with_account()
        _, destination_b = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin_account["account_key"], origin_client["client_key"], 10000)

        payload_a = PayloadGenerator.create_transfer_payload(destination_a["account_key"], amount=8000)
        payload_b = PayloadGenerator.create_transfer_payload(destination_b["account_key"], amount=8000)

        def send(payload):
            return RequestGenerator.POST_transaction(
                origin_account["account_key"], payload, origin_client["client_key"]
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(send, [payload_a, payload_b]))

        statuses = sorted(status for status, _response in results)
        assert statuses == [201, 422]

        _, origin = RequestGenerator.GET_account(origin_account["account_key"], origin_client["client_key"])
        assert origin["balance"] == 1800

    def test_two_concurrent_replays_execute_only_once(self):
        DbUtils.rollback()
        origin_client, origin_account = ObjectGenerator.create_client_with_account()
        destination_client, destination_account = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin_account["account_key"], origin_client["client_key"], 30000)
        payload = PayloadGenerator.create_transfer_payload(destination_account["account_key"], amount=10000)

        def send(_index):
            return RequestGenerator.POST_transaction(
                origin_account["account_key"], payload, origin_client["client_key"]
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(send, [0, 1]))

        assert [status for status, _ in results] == [201, 201]
        assert results[0][1] == results[1][1]

        _, origin = RequestGenerator.GET_account(origin_account["account_key"], origin_client["client_key"])
        _, destination = RequestGenerator.GET_account(
            destination_account["account_key"], destination_client["client_key"]
        )
        assert origin["balance"] == 19800
        assert destination["balance"] == 10000


class TestTransferRiskControls:
    def test_transfer_at_single_limit_is_accepted(self):
        owner, origin = ObjectGenerator.create_client_with_account()
        _receiver, destination = ObjectGenerator.create_client_with_account()
        RequestGenerator.PUT_account_limits(
            origin["account_key"], {"single_transfer_limit": 10000, "daily_transfer_limit": 30000}
        )
        ObjectGenerator.deposit(origin["account_key"], owner["client_key"], 20000)
        payload = PayloadGenerator.create_transfer_payload(destination["account_key"], amount=10000)
        status, _ = RequestGenerator.POST_transaction(origin["account_key"], payload, owner["client_key"])
        assert status == 201

    def test_transfer_above_single_limit_has_no_financial_effect(self):
        owner, origin = ObjectGenerator.create_client_with_account()
        receiver, destination = ObjectGenerator.create_client_with_account()
        RequestGenerator.PUT_account_limits(
            origin["account_key"], {"single_transfer_limit": 10000, "daily_transfer_limit": 30000}
        )
        ObjectGenerator.deposit(origin["account_key"], owner["client_key"], 50000)
        payload = PayloadGenerator.create_transfer_payload(destination["account_key"], amount=10001)
        status, response = RequestGenerator.POST_transaction(origin["account_key"], payload, owner["client_key"])
        assert status == 422
        assert response["code"] == "QIT004004"
        _, origin_after = RequestGenerator.GET_account(origin["account_key"], owner["client_key"])
        _, destination_after = RequestGenerator.GET_account(destination["account_key"], receiver["client_key"])
        assert origin_after["balance"] == 50000
        assert destination_after["balance"] == 0

    def test_daily_limit_accumulates_only_transfer_amounts(self):
        owner, origin = ObjectGenerator.create_client_with_account()
        receiver, destination = ObjectGenerator.create_client_with_account()
        RequestGenerator.PUT_account_limits(
            origin["account_key"], {"single_transfer_limit": 10000, "daily_transfer_limit": 15000}
        )
        ObjectGenerator.deposit(origin["account_key"], owner["client_key"], 50000)

        first = PayloadGenerator.create_transfer_payload(destination["account_key"], amount=10000)
        status, _ = RequestGenerator.POST_transaction(origin["account_key"], first, owner["client_key"])
        assert status == 201

        second = PayloadGenerator.create_transfer_payload(destination["account_key"], amount=5001)
        status, response = RequestGenerator.POST_transaction(origin["account_key"], second, owner["client_key"])
        assert status == 422
        assert response["code"] == "QIT004005"

        _, origin_after = RequestGenerator.GET_account(origin["account_key"], owner["client_key"])
        _, destination_after = RequestGenerator.GET_account(destination["account_key"], receiver["client_key"])
        assert origin_after["balance"] == 39800
        assert destination_after["balance"] == 10000

    def test_concurrent_transfers_cannot_bypass_daily_limit(self):
        DbUtils.rollback()
        owner, origin = ObjectGenerator.create_client_with_account()
        _receiver_a, destination_a = ObjectGenerator.create_client_with_account()
        _receiver_b, destination_b = ObjectGenerator.create_client_with_account()
        RequestGenerator.PUT_account_limits(
            origin["account_key"], {"single_transfer_limit": 10000, "daily_transfer_limit": 10000}
        )
        ObjectGenerator.deposit(origin["account_key"], owner["client_key"], 30000)
        payloads = [
            PayloadGenerator.create_transfer_payload(destination_a["account_key"], amount=8000),
            PayloadGenerator.create_transfer_payload(destination_b["account_key"], amount=8000),
        ]

        def send(payload):
            return RequestGenerator.POST_transaction(origin["account_key"], payload, owner["client_key"])

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(send, payloads))

        assert sorted(status for status, _body in results) == [201, 422]
        rejected = [body for status, body in results if status == 422]
        assert rejected[0]["code"] == "QIT004005"

        _status, origin_after = RequestGenerator.GET_account(origin["account_key"], owner["client_key"])
        assert origin_after["balance"] == 21800

    def test_limit_check_does_not_replace_balance_check(self):
        owner, origin = ObjectGenerator.create_client_with_account()
        _receiver, destination = ObjectGenerator.create_client_with_account()
        RequestGenerator.PUT_account_limits(
            origin["account_key"], {"single_transfer_limit": 10000, "daily_transfer_limit": 20000}
        )
        ObjectGenerator.deposit(origin["account_key"], owner["client_key"], 10000)
        payload = PayloadGenerator.create_transfer_payload(destination["account_key"], amount=10000)
        status, response = RequestGenerator.POST_transaction(origin["account_key"], payload, owner["client_key"])
        assert status == 422
        assert response["code"] == "QIT004001"

    def test_blocked_origin_cannot_transfer(self):
        owner, origin = ObjectGenerator.create_client_with_account()
        _receiver, destination = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin["account_key"], owner["client_key"], 20000)
        RequestGenerator.PUT_account_status(origin["account_key"], "blocked")
        payload = PayloadGenerator.create_transfer_payload(destination["account_key"], amount=1000)
        status, response = RequestGenerator.POST_transaction(origin["account_key"], payload, owner["client_key"])
        assert status == 423
        assert response["code"] == "QIT003003"

    def test_blocked_destination_cannot_receive_transfer(self):
        owner, origin = ObjectGenerator.create_client_with_account()
        receiver, destination = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin["account_key"], owner["client_key"], 20000)
        RequestGenerator.PUT_account_status(destination["account_key"], "blocked")
        payload = PayloadGenerator.create_transfer_payload(destination["account_key"], amount=1000)
        status, response = RequestGenerator.POST_transaction(origin["account_key"], payload, owner["client_key"])
        assert status == 423
        assert response["code"] == "QIT003003"
        _, origin_after = RequestGenerator.GET_account(origin["account_key"], owner["client_key"])
        _, destination_after = RequestGenerator.GET_account(destination["account_key"], receiver["client_key"])
        assert origin_after["balance"] == 20000
        assert destination_after["balance"] == 0

    def test_committed_transfer_replay_survives_later_account_block(self):
        owner, origin = ObjectGenerator.create_client_with_account()
        _receiver, destination = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin["account_key"], owner["client_key"], 20000)
        payload = PayloadGenerator.create_transfer_payload(destination["account_key"], amount=1000)
        status, first = RequestGenerator.POST_transaction(origin["account_key"], payload, owner["client_key"])
        assert status == 201
        RequestGenerator.PUT_account_status(origin["account_key"], "blocked")
        status, replay = RequestGenerator.POST_transaction(origin["account_key"], payload, owner["client_key"])
        assert status == 201
        assert replay == first
