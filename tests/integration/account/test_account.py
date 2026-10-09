from tests.utils import ObjectGenerator, RequestGenerator


class TestAccount:
    def test_create_account_with_zero_balance(self):
        client = ObjectGenerator.create_client()
        status, response = RequestGenerator.POST_account(
            client["client_key"], requester_client_key=client["client_key"]
        )
        assert status == 201
        account_key = response["account_key"]

        status, response = RequestGenerator.GET_account(account_key, client["client_key"])
        assert status == 200
        assert response["account_key"] == account_key
        assert response["client_key"] == client["client_key"]
        assert response["balance"] == 0
        assert "id" not in response

    def test_client_can_have_more_than_one_account(self):
        client = ObjectGenerator.create_client()
        first = ObjectGenerator.create_account(client["client_key"])
        second = ObjectGenerator.create_account(client["client_key"])
        assert first["account_key"] != second["account_key"]

    def test_create_account_for_unknown_client_returns_404(self):
        unknown = "00000000-0000-4000-8000-000000000000"
        status, response = RequestGenerator.POST_account(unknown, requester_client_key=unknown)
        assert status == 404
        assert response["code"] == "QIT002001"

    def test_create_account_requires_identity(self):
        client = ObjectGenerator.create_client()
        status, response = RequestGenerator.POST_account(client["client_key"])
        assert status == 401
        assert response["code"] == "QIT005001"

    def test_cannot_create_account_for_another_client(self):
        first = ObjectGenerator.create_client()
        second = ObjectGenerator.create_client()
        status, response = RequestGenerator.POST_account(
            first["client_key"], requester_client_key=second["client_key"]
        )
        assert status == 404
        assert response["code"] == "QIT002001"

    def test_get_account_requires_identity(self):
        client, account = ObjectGenerator.create_client_with_account()
        status, response = RequestGenerator.GET_account(account["account_key"])
        assert status == 401
        assert response["code"] == "QIT005001"

    def test_cannot_read_another_clients_account(self):
        first_client, first_account = ObjectGenerator.create_client_with_account()
        second_client = ObjectGenerator.create_client()
        status, response = RequestGenerator.GET_account(
            first_account["account_key"], second_client["client_key"]
        )
        assert status == 404
        assert response["code"] == "QIT003001"
