from concurrent.futures import ThreadPoolExecutor

from tests.utils import DbUtils, ObjectGenerator, RequestGenerator


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
        assert response["status"] == "active"
        assert response["single_transfer_limit"] == 500000
        assert response["daily_transfer_limit"] == 2000000
        assert "id" not in response

    def test_client_cannot_open_second_account_in_mvp(self):
        client = ObjectGenerator.create_client()
        ObjectGenerator.create_account(client["client_key"])

        status, response = RequestGenerator.POST_account(
            client["client_key"], requester_client_key=client["client_key"]
        )
        assert status == 409
        assert response["code"] == "QIT003002"

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


    def test_unknown_account_returns_404(self):
        client = ObjectGenerator.create_client()
        unknown = "00000000-0000-4000-8000-000000000000"
        status, response = RequestGenerator.GET_account(unknown, client["client_key"])
        assert status == 404
        assert response["code"] == "QIT003001"

    def test_two_concurrent_account_creates_create_only_one_account(self):
        DbUtils.rollback()
        client = ObjectGenerator.create_client()

        def create(_):
            return RequestGenerator.POST_account(
                client["client_key"], requester_client_key=client["client_key"]
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(create, [0, 1]))

        statuses = sorted(status for status, _ in results)
        assert statuses == [201, 409]
        duplicate = next(body for status, body in results if status == 409)
        assert duplicate["code"] == "QIT003002"

        created = next(body for status, body in results if status == 201)
        status, account = RequestGenerator.GET_account(
            created["account_key"], client["client_key"]
        )
        assert status == 200
        assert account["balance"] == 0


class TestAccountRiskConfiguration:
    def test_internal_limit_configuration_updates_account(self):
        client, account = ObjectGenerator.create_client_with_account()
        status, response = RequestGenerator.PUT_account_limits(
            account["account_key"],
            {"single_transfer_limit": 10000, "daily_transfer_limit": 25000},
        )
        assert status == 200
        assert response == {
            "account_key": account["account_key"],
            "single_transfer_limit": 10000,
            "daily_transfer_limit": 25000,
        }

        _, current = RequestGenerator.GET_account(account["account_key"], client["client_key"])
        assert current["single_transfer_limit"] == 10000
        assert current["daily_transfer_limit"] == 25000

    def test_daily_limit_cannot_be_lower_than_single_limit(self):
        _client, account = ObjectGenerator.create_client_with_account()
        status, response = RequestGenerator.PUT_account_limits(
            account["account_key"],
            {"single_transfer_limit": 20000, "daily_transfer_limit": 10000},
        )
        assert status == 422
        assert response["code"] == "QIT003006"

    def test_account_can_be_blocked_and_reactivated_by_internal_status_event(self):
        client, account = ObjectGenerator.create_client_with_account()
        status, blocked = RequestGenerator.PUT_account_status(account["account_key"], "blocked")
        assert status == 200
        assert blocked["status"] == "blocked"
        _, current = RequestGenerator.GET_account(account["account_key"], client["client_key"])
        assert current["status"] == "blocked"

        status, active = RequestGenerator.PUT_account_status(account["account_key"], "active")
        assert status == 200
        assert active["status"] == "active"

    def test_account_with_balance_cannot_be_closed(self):
        client, account = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(account["account_key"], client["client_key"], 1000)
        status, response = RequestGenerator.PUT_account_status(account["account_key"], "closed")
        assert status == 409
        assert response["code"] == "QIT003004"

    def test_closed_account_is_final(self):
        _client, account = ObjectGenerator.create_client_with_account()
        status, closed = RequestGenerator.PUT_account_status(account["account_key"], "closed")
        assert status == 200
        assert closed["status"] == "closed"
        status, response = RequestGenerator.PUT_account_status(account["account_key"], "active")
        assert status == 409
        assert response["code"] == "QIT003005"
