from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from tests.utils import DbUtils, ObjectGenerator, PayloadGenerator, RequestGenerator


class TestFinancialInvariants:
    def test_request_control_key_cannot_change_operation_type(self):
        origin_client, origin_account = ObjectGenerator.create_client_with_account()
        _, destination_account = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin_account["account_key"], origin_client["client_key"], 10000)
        key = str(uuid4())

        deposit = PayloadGenerator.create_deposit_payload(amount=1000, request_control_key=key)
        status, _ = RequestGenerator.POST_transaction(
            origin_account["account_key"], deposit, origin_client["client_key"]
        )
        assert status == 201

        transfer = PayloadGenerator.create_transfer_payload(
            destination_account["account_key"], amount=1000, request_control_key=key
        )
        status, response = RequestGenerator.POST_transaction(
            origin_account["account_key"], transfer, origin_client["client_key"]
        )
        assert status == 409
        assert response["code"] == "QIT004003"

    def test_failed_transfer_creates_no_effect_in_destination_statement(self):
        origin_client, origin_account = ObjectGenerator.create_client_with_account()
        destination_client, destination_account = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin_account["account_key"], origin_client["client_key"], 1000)

        payload = PayloadGenerator.create_transfer_payload(destination_account["account_key"], amount=1000)
        status, response = RequestGenerator.POST_transaction(
            origin_account["account_key"], payload, origin_client["client_key"]
        )
        assert status == 422
        assert response["code"] == "QIT004001"

        _, destination_statement = RequestGenerator.GET_transactions(
            destination_account["account_key"], destination_client["client_key"]
        )
        assert destination_statement["data"] == []

    def test_many_concurrent_distinct_deposits_are_all_preserved(self):
        DbUtils.rollback()
        client, account = ObjectGenerator.create_client_with_account()
        payloads = [PayloadGenerator.create_deposit_payload(amount=100) for _ in range(12)]

        def send(payload):
            return RequestGenerator.POST_transaction(
                account["account_key"], payload, client["client_key"]
            )

        with ThreadPoolExecutor(max_workers=12) as executor:
            results = list(executor.map(send, payloads))

        assert all(status == 201 for status, _ in results)
        _, current = RequestGenerator.GET_account(account["account_key"], client["client_key"])
        assert current["balance"] == 1200

        _, statement = RequestGenerator.GET_transactions(
            account["account_key"], client["client_key"]
        )
        assert len(statement["data"]) == 12
        assert sum(row["balance_effect"] for row in statement["data"]) == 1200

    def test_concurrent_deposit_replay_storm_credits_once(self):
        DbUtils.rollback()
        client, account = ObjectGenerator.create_client_with_account()
        payload = PayloadGenerator.create_deposit_payload(amount=5000)

        def send(_):
            return RequestGenerator.POST_transaction(
                account["account_key"], payload, client["client_key"]
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(send, range(8)))

        assert all(status == 201 for status, _ in results)
        first = results[0][1]
        assert all(body == first for _, body in results)

        _, current = RequestGenerator.GET_account(account["account_key"], client["client_key"])
        assert current["balance"] == 5000
        _, statement = RequestGenerator.GET_transactions(
            account["account_key"], client["client_key"]
        )
        assert len(statement["data"]) == 1
        assert statement["data"][0]["type"] == "deposit"

    def test_multi_account_scenario_reconstructs_every_balance_from_statement(self):
        DbUtils.rollback()
        client_a, account_a = ObjectGenerator.create_client_with_account()
        client_b, account_b = ObjectGenerator.create_client_with_account()
        client_c, account_c = ObjectGenerator.create_client_with_account()

        ObjectGenerator.deposit(account_a["account_key"], client_a["client_key"], 50000)
        ObjectGenerator.deposit(account_b["account_key"], client_b["client_key"], 30000)

        operations = [
            (client_a, account_a, account_b, 10000),
            (client_b, account_b, account_c, 5000),
            (client_a, account_a, account_c, 7000),
            (client_b, account_b, account_a, 3000),
        ]
        for owner, origin, destination, amount in operations:
            payload = PayloadGenerator.create_transfer_payload(destination["account_key"], amount=amount)
            status, _ = RequestGenerator.POST_transaction(
                origin["account_key"], payload, owner["client_key"]
            )
            assert status == 201

        for client, account in [
            (client_a, account_a),
            (client_b, account_b),
            (client_c, account_c),
        ]:
            _, current = RequestGenerator.GET_account(account["account_key"], client["client_key"])
            _, statement = RequestGenerator.GET_transactions(
                account["account_key"], client["client_key"], {"limit": 100, "page": 0}
            )
            reconstructed = sum(row["balance_effect"] for row in statement["data"])
            assert reconstructed == current["balance"]
            assert current["balance"] >= 0
