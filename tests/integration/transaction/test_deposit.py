from uuid import uuid4

from tests.utils import ObjectGenerator, PayloadGenerator, RequestGenerator


class TestDeposit:
    def test_deposit_increases_balance_and_is_recorded(self):
        client, account = ObjectGenerator.create_client_with_account()
        payload = PayloadGenerator.create_deposit_payload(amount=50000)

        status, response = RequestGenerator.POST_transaction(
            account["account_key"], payload, client["client_key"]
        )
        assert status == 201
        assert response["type"] == "deposit"
        assert response["amount"] == 50000
        assert response["fee_amount"] == 0
        assert response["origin_account_key"] is None
        assert response["destination_account_key"] == account["account_key"]
        assert response["request_control_key"] == payload["request_control_key"]

        status, account_response = RequestGenerator.GET_account(
            account["account_key"], client["client_key"]
        )
        assert status == 200
        assert account_response["balance"] == 50000

    def test_deposit_is_idempotent(self):
        client, account = ObjectGenerator.create_client_with_account()
        payload = PayloadGenerator.create_deposit_payload(amount=50000)

        status, first = RequestGenerator.POST_transaction(
            account["account_key"], payload, client["client_key"]
        )
        assert status == 201
        status, second = RequestGenerator.POST_transaction(
            account["account_key"], payload, client["client_key"]
        )
        assert status == 201
        assert first == second

        status, account_response = RequestGenerator.GET_account(
            account["account_key"], client["client_key"]
        )
        assert account_response["balance"] == 50000

    def test_same_request_control_key_with_different_amount_conflicts(self):
        client, account = ObjectGenerator.create_client_with_account()
        key = str(uuid4())
        first = PayloadGenerator.create_deposit_payload(amount=1000, request_control_key=key)
        second = PayloadGenerator.create_deposit_payload(amount=2000, request_control_key=key)

        status, _ = RequestGenerator.POST_transaction(account["account_key"], first, client["client_key"])
        assert status == 201
        status, response = RequestGenerator.POST_transaction(
            account["account_key"], second, client["client_key"]
        )
        assert status == 409
        assert response["code"] == "QIT004003"

    def test_same_request_control_key_cannot_be_reused_in_another_account(self):
        first_client, first_account = ObjectGenerator.create_client_with_account()
        second_client, second_account = ObjectGenerator.create_client_with_account()
        key = str(uuid4())

        first = PayloadGenerator.create_deposit_payload(amount=1000, request_control_key=key)
        status, _ = RequestGenerator.POST_transaction(
            first_account["account_key"], first, first_client["client_key"]
        )
        assert status == 201

        second = PayloadGenerator.create_deposit_payload(amount=1000, request_control_key=key)
        status, response = RequestGenerator.POST_transaction(
            second_account["account_key"], second, second_client["client_key"]
        )
        assert status == 409
        assert response["code"] == "QIT004003"

    def test_schema_refuses_zero_negative_and_float_amount(self):
        client, account = ObjectGenerator.create_client_with_account()
        for amount in [0, -1, 10.5]:
            payload = PayloadGenerator.create_deposit_payload()
            payload["amount"] = amount
            status, response = RequestGenerator.POST_transaction(
                account["account_key"], payload, client["client_key"]
            )
            assert status == 400
            assert response["code"] == "QIT000001"

    def test_schema_refuses_destination_on_deposit(self):
        client, account = ObjectGenerator.create_client_with_account()
        payload = PayloadGenerator.create_deposit_payload()
        payload["destination_account_key"] = account["account_key"]
        status, response = RequestGenerator.POST_transaction(
            account["account_key"], payload, client["client_key"]
        )
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_deposit_requires_identity(self):
        client, account = ObjectGenerator.create_client_with_account()
        payload = PayloadGenerator.create_deposit_payload()
        status, response = RequestGenerator.POST_transaction(account["account_key"], payload)
        assert status == 401
        assert response["code"] == "QIT005001"

    def test_cannot_deposit_in_another_clients_account(self):
        owner, account = ObjectGenerator.create_client_with_account()
        attacker = ObjectGenerator.create_client()
        payload = PayloadGenerator.create_deposit_payload()
        status, response = RequestGenerator.POST_transaction(
            account["account_key"], payload, attacker["client_key"]
        )
        assert status == 404
        assert response["code"] == "QIT003001"
    def test_known_idempotency_key_does_not_bypass_ownership(self):
        owner, account = ObjectGenerator.create_client_with_account()
        attacker = ObjectGenerator.create_client()
        payload = PayloadGenerator.create_deposit_payload(amount=1234)
        status, _ = RequestGenerator.POST_transaction(
            account["account_key"], payload, owner["client_key"]
        )
        assert status == 201

        status, response = RequestGenerator.POST_transaction(
            account["account_key"], payload, attacker["client_key"]
        )
        assert status == 404
        assert response["code"] == "QIT003001"

