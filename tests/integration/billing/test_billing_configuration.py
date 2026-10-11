import pytest

from tests.utils import DbUtils, ObjectGenerator, PayloadGenerator, RequestGenerator


@pytest.fixture(autouse=True)
def reset_billing_policy_between_tests():
    DbUtils.rollback()
    yield
    DbUtils.rollback()


class TestBillingConfiguration:
    def test_default_transfer_fee_policy_is_fixed_two_reais(self):
        status, body = RequestGenerator.GET_transfer_billing_configuration()
        assert status == 200
        assert body == {
            "operation_type": "transfer",
            "expense_type": "fixed_amount",
            "amount": 200,
        }

    def test_operator_can_change_fixed_transfer_fee_and_new_transfer_uses_it(self):
        status, body = RequestGenerator.PUT_transfer_billing_configuration(
            {"expense_type": "fixed_amount", "amount": 250}
        )
        assert status == 200
        assert body["amount"] == 250

        origin_client, origin = ObjectGenerator.create_client_with_account()
        _destination_client, destination = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin["account_key"], origin_client["client_key"], 50000)
        payload = PayloadGenerator.create_transfer_payload(destination["account_key"], amount=10000)
        status, transfer = RequestGenerator.POST_transaction(
            origin["account_key"], payload, requester_client_key=origin_client["client_key"]
        )
        assert status == 201
        assert transfer["fee_amount"] == 250

        status, account = RequestGenerator.GET_account(
            origin["account_key"], requester_client_key=origin_client["client_key"]
        )
        assert status == 200
        assert account["balance"] == 39750

    def test_operator_can_use_percentage_fee_without_float(self):
        status, body = RequestGenerator.PUT_transfer_billing_configuration(
            {"expense_type": "percentage", "percentage_basis_points": 150}
        )
        assert status == 200
        assert body == {
            "operation_type": "transfer",
            "expense_type": "percentage",
            "percentage_basis_points": 150,
        }

        origin_client, origin = ObjectGenerator.create_client_with_account()
        _destination_client, destination = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin["account_key"], origin_client["client_key"], 50000)
        payload = PayloadGenerator.create_transfer_payload(destination["account_key"], amount=10000)
        status, transfer = RequestGenerator.POST_transaction(
            origin["account_key"], payload, requester_client_key=origin_client["client_key"]
        )
        assert status == 201
        assert transfer["fee_amount"] == 150

    def test_percentage_fee_rounds_half_up_to_integer_cent(self):
        RequestGenerator.PUT_transfer_billing_configuration(
            {"expense_type": "percentage", "percentage_basis_points": 50}
        )
        origin_client, origin = ObjectGenerator.create_client_with_account()
        _destination_client, destination = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin["account_key"], origin_client["client_key"], 50000)
        payload = PayloadGenerator.create_transfer_payload(destination["account_key"], amount=100)
        status, transfer = RequestGenerator.POST_transaction(
            origin["account_key"], payload, requester_client_key=origin_client["client_key"]
        )
        assert status == 201
        assert transfer["fee_amount"] == 1

    def test_billing_configuration_rejects_ambiguous_shape(self):
        status, body = RequestGenerator.PUT_transfer_billing_configuration(
            {"expense_type": "fixed_amount", "amount": 200, "percentage_basis_points": 150}
        )
        assert status == 400
        assert body["code"] == "QIT000001"

    def test_historical_fee_remains_append_only_after_policy_change(self):
        origin_client, origin = ObjectGenerator.create_client_with_account()
        _destination_client, destination = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin["account_key"], origin_client["client_key"], 50000)
        payload = PayloadGenerator.create_transfer_payload(destination["account_key"], amount=10000)
        status, transfer = RequestGenerator.POST_transaction(
            origin["account_key"], payload, requester_client_key=origin_client["client_key"]
        )
        assert status == 201
        assert transfer["fee_amount"] == 200

        RequestGenerator.PUT_transfer_billing_configuration(
            {"expense_type": "fixed_amount", "amount": 350}
        )
        status, statement = RequestGenerator.GET_transactions(
            origin["account_key"], requester_client_key=origin_client["client_key"]
        )
        assert status == 200
        fee_rows = [row for row in statement["data"] if row["type"] == "fee" and row["operation_key"] == transfer["operation_key"]]
        assert len(fee_rows) == 1
        assert fee_rows[0]["amount"] == 200

    def test_committed_transfer_replay_keeps_original_fee_after_policy_change(self):
        origin_client, origin = ObjectGenerator.create_client_with_account()
        _destination_client, destination = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin["account_key"], origin_client["client_key"], 50000)
        payload = PayloadGenerator.create_transfer_payload(destination["account_key"], amount=10000)
        status, first = RequestGenerator.POST_transaction(
            origin["account_key"], payload, requester_client_key=origin_client["client_key"]
        )
        assert status == 201
        assert first["fee_amount"] == 200

        RequestGenerator.PUT_transfer_billing_configuration(
            {"expense_type": "fixed_amount", "amount": 350}
        )
        status, replay = RequestGenerator.POST_transaction(
            origin["account_key"], payload, requester_client_key=origin_client["client_key"]
        )
        assert status == 201
        assert replay == first
