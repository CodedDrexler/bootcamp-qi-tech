from tests.utils import ObjectGenerator, PayloadGenerator, RequestGenerator


MAX_TRANSACTION_AMOUNT = 100000000  # R$ 1.000.000,00: teto técnico do contrato PF do MVP


class TestMoneyBoundaries:
    def test_maximum_contract_amount_is_accepted_exactly_for_confirmed_funding(self):
        client, account = ObjectGenerator.create_client_with_account()
        payload = PayloadGenerator.create_deposit_payload(amount=MAX_TRANSACTION_AMOUNT)
        status, transaction = RequestGenerator.POST_transaction(
            account["account_key"], payload, client["client_key"]
        )
        assert status == 201
        assert transaction["amount"] == MAX_TRANSACTION_AMOUNT

        status, account_after = RequestGenerator.GET_account(account["account_key"], client["client_key"])
        assert status == 200
        assert account_after["balance"] == MAX_TRANSACTION_AMOUNT

    def test_value_above_contract_max_is_rejected_before_business_logic(self):
        client, account = ObjectGenerator.create_client_with_account()
        payload = PayloadGenerator.create_deposit_payload(amount=MAX_TRANSACTION_AMOUNT + 1)
        status, response = RequestGenerator.POST_transaction(
            account["account_key"], payload, client["client_key"]
        )
        assert status == 400
        assert response["code"] == "QIT000001"

        status, account_after = RequestGenerator.GET_account(account["account_key"], client["client_key"])
        assert status == 200
        assert account_after["balance"] == 0
