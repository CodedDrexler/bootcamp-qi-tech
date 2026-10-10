from tests.utils import INTERNAL_TOKEN, ObjectGenerator
from tests.utils.requisition import ClientRequisition


class TestForbiddenMutationSurface:
    def test_account_balance_cannot_be_changed_by_patch(self):
        client, account = ObjectGenerator.create_client_with_account()
        response = ClientRequisition.send(
            "PATCH",
            f"/account/{account['account_key']}",
            payload={"balance": 999999999},
            headers={
                "INTERNAL-TOKEN": INTERNAL_TOKEN,
                "X-CLIENT-KEY": client["client_key"],
            },
        )
        assert response.response_status == 405
        assert response.response_json["code"] == "QIT000405"

    def test_transaction_history_has_no_update_surface(self):
        client, account = ObjectGenerator.create_client_with_account()
        response = ClientRequisition.send(
            "PUT",
            f"/account/{account['account_key']}/transaction",
            payload={"amount": 1},
            headers={
                "INTERNAL-TOKEN": INTERNAL_TOKEN,
                "X-CLIENT-KEY": client["client_key"],
            },
        )
        assert response.response_status == 405
        assert response.response_json["code"] == "QIT000405"

    def test_transaction_history_has_no_delete_surface(self):
        client, account = ObjectGenerator.create_client_with_account()
        response = ClientRequisition.send(
            "DELETE",
            f"/account/{account['account_key']}/transactions",
            headers={
                "INTERNAL-TOKEN": INTERNAL_TOKEN,
                "X-CLIENT-KEY": client["client_key"],
            },
        )
        assert response.response_status == 405
        assert response.response_json["code"] == "QIT000405"

    def test_account_creation_body_cannot_inject_initial_balance(self):
        client = ObjectGenerator.create_client()
        response = ClientRequisition.send(
            "POST",
            f"/client/{client['client_key']}/account",
            payload={"balance": 999999999},
            headers={
                "INTERNAL-TOKEN": INTERNAL_TOKEN,
                "X-CLIENT-KEY": client["client_key"],
            },
        )
        assert response.response_status == 201
        account_key = response.response_json["account_key"]

        response = ClientRequisition.send(
            "GET",
            f"/account/{account_key}",
            headers={
                "INTERNAL-TOKEN": INTERNAL_TOKEN,
                "X-CLIENT-KEY": client["client_key"],
            },
        )
        assert response.response_status == 200
        assert response.response_json["balance"] == 0
