from uuid import uuid4

from tests.utils import ObjectGenerator, PayloadGenerator, RequestGenerator


class TestValidationMatrix:
    def test_client_schema_rejects_empty_payload(self):
        status, response = RequestGenerator.POST_client({})
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_client_schema_rejects_name_outside_contract(self):
        for name in ["A", "A" * 256]:
            payload = PayloadGenerator.create_client_payload(name=name)
            status, response = RequestGenerator.POST_client(payload)
            assert status == 400
            assert response["code"] == "QIT000001"

    def test_client_schema_rejects_birth_date_wrong_format(self):
        payload = PayloadGenerator.create_client_payload(birth_date="12/03/1994")
        status, response = RequestGenerator.POST_client(payload)
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_transaction_rejects_unknown_type(self):
        client, account = ObjectGenerator.create_client_with_account()
        payload = PayloadGenerator.create_deposit_payload(amount=100)
        payload["type"] = "withdraw"
        status, response = RequestGenerator.POST_transaction(
            account["account_key"], payload, client["client_key"]
        )
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_transaction_rejects_extra_property(self):
        client, account = ObjectGenerator.create_client_with_account()
        payload = PayloadGenerator.create_deposit_payload(amount=100)
        payload["force"] = True
        status, response = RequestGenerator.POST_transaction(
            account["account_key"], payload, client["client_key"]
        )
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_transaction_rejects_malformed_request_control_key(self):
        client, account = ObjectGenerator.create_client_with_account()
        payload = PayloadGenerator.create_deposit_payload(amount=100, request_control_key="not-a-uuid")
        status, response = RequestGenerator.POST_transaction(
            account["account_key"], payload, client["client_key"]
        )
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_transaction_rejects_non_integer_and_excessive_amounts(self):
        client, account = ObjectGenerator.create_client_with_account()
        for amount in ["100", True, 100000001]:
            payload = PayloadGenerator.create_deposit_payload(amount=amount)
            status, response = RequestGenerator.POST_transaction(
                account["account_key"], payload, client["client_key"]
            )
            assert status == 400
            assert response["code"] == "QIT000001"

    def test_transfer_rejects_malformed_destination_key(self):
        client, account = ObjectGenerator.create_client_with_account()
        payload = {
            "request_control_key": str(uuid4()),
            "type": "transfer",
            "amount": 100,
            "destination_account_key": "not-a-uuid",
        }
        status, response = RequestGenerator.POST_transaction(
            account["account_key"], payload, client["client_key"]
        )
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_statement_page_beyond_end_is_empty_and_last(self):
        client, account = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(account["account_key"], client["client_key"], 100)
        status, response = RequestGenerator.GET_transactions(
            account["account_key"], client["client_key"], {"limit": 20, "page": 99}
        )
        assert status == 200
        assert response["data"] == []
        assert response["page"] == 99
        assert response["is_last_page"] is True
