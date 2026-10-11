from datetime import datetime
from uuid import UUID

from tests.utils import ObjectGenerator, PayloadGenerator, RequestGenerator


def assert_uuid(value: str) -> None:
    assert str(UUID(value)) == value.lower()


def assert_iso_datetime(value: str) -> None:
    assert datetime.fromisoformat(value) is not None


class TestPublicResponseContract:
    def test_client_create_and_get_have_exact_public_shape(self):
        payload = PayloadGenerator.create_client_payload(name="Ana Contract")
        status, created = RequestGenerator.POST_client(payload)

        assert status == 201
        assert set(created) == {"client_key"}
        assert_uuid(created["client_key"])

        status, client = RequestGenerator.GET_client(
            created["client_key"],
            requester_client_key=created["client_key"],
        )
        assert status == 200
        assert set(client) == {
            "client_key",
            "name",
            "document_number",
            "birth_date",
            "created_at",
        }
        assert client["client_key"] == created["client_key"]
        assert client["name"] == payload["name"]
        assert client["document_number"] == payload["document_number"]
        assert client["birth_date"] == payload["birth_date"]
        assert_iso_datetime(client["created_at"])
        assert "id" not in client

    def test_account_create_and_get_have_exact_public_shape(self):
        client = ObjectGenerator.create_client()

        status, created = RequestGenerator.POST_account(
            client["client_key"],
            requester_client_key=client["client_key"],
        )
        assert status == 201
        assert set(created) == {"account_key"}
        assert_uuid(created["account_key"])

        status, account = RequestGenerator.GET_account(
            created["account_key"],
            requester_client_key=client["client_key"],
        )
        assert status == 200
        assert set(account) == {"account_key", "client_key", "status", "balance", "single_transfer_limit", "daily_transfer_limit", "created_at"}
        assert account["account_key"] == created["account_key"]
        assert account["client_key"] == client["client_key"]
        assert account["balance"] == 0
        assert account["status"] == "active"
        assert account["single_transfer_limit"] == 500000
        assert account["daily_transfer_limit"] == 2000000
        assert_iso_datetime(account["created_at"])
        assert "id" not in account

    def test_deposit_response_has_exact_shape_and_replay_is_identical(self):
        client, account = ObjectGenerator.create_client_with_account()
        payload = PayloadGenerator.create_deposit_payload(amount=12345)

        first_status, first = RequestGenerator.POST_transaction(
            account["account_key"], payload, client["client_key"]
        )
        second_status, second = RequestGenerator.POST_transaction(
            account["account_key"], payload, client["client_key"]
        )

        assert first_status == second_status == 201
        assert first == second
        assert set(first) == {
            "transaction_key",
            "operation_key",
            "request_control_key",
            "type",
            "origin_account_key",
            "destination_account_key",
            "amount",
            "fee_amount",
            "created_at",
        }
        assert_uuid(first["transaction_key"])
        assert_uuid(first["operation_key"])
        assert first["request_control_key"] == payload["request_control_key"]
        assert first["type"] == "deposit"
        assert first["origin_account_key"] is None
        assert first["destination_account_key"] == account["account_key"]
        assert first["amount"] == 12345
        assert first["fee_amount"] == 0
        assert_iso_datetime(first["created_at"])

    def test_transfer_response_has_exact_shape_and_replay_is_identical(self):
        owner, origin = ObjectGenerator.create_client_with_account()
        _, destination = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin["account_key"], owner["client_key"], 50000)
        payload = PayloadGenerator.create_transfer_payload(
            destination["account_key"], amount=20000
        )

        first_status, first = RequestGenerator.POST_transaction(
            origin["account_key"], payload, owner["client_key"]
        )
        second_status, second = RequestGenerator.POST_transaction(
            origin["account_key"], payload, owner["client_key"]
        )

        assert first_status == second_status == 201
        assert first == second
        assert set(first) == {
            "transaction_key",
            "operation_key",
            "request_control_key",
            "type",
            "origin_account_key",
            "destination_account_key",
            "amount",
            "fee_amount",
            "created_at",
        }
        assert_uuid(first["transaction_key"])
        assert_uuid(first["operation_key"])
        assert first["request_control_key"] == payload["request_control_key"]
        assert first["type"] == "transfer"
        assert first["origin_account_key"] == origin["account_key"]
        assert first["destination_account_key"] == destination["account_key"]
        assert first["amount"] == 20000
        assert first["fee_amount"] == 200
        assert_iso_datetime(first["created_at"])
