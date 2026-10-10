from tests.utils import INTERNAL_TOKEN, ObjectGenerator, RequestGenerator
from tests.utils.requisition import ClientRequisition


def assert_no_internal_id(value):
    if isinstance(value, dict):
        assert "id" not in value
        for child in value.values():
            assert_no_internal_id(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_internal_id(child)


class TestRuntimeContract:
    def test_banking_route_rejects_invalid_internal_token(self):
        client = ObjectGenerator.create_client()
        response = ClientRequisition.send(
            "GET",
            f"/client/{client['client_key']}",
            headers={
                "INTERNAL-TOKEN": "invalid-token",
                "X-CLIENT-KEY": client["client_key"],
            },
        )
        assert response.response_status == 403
        assert response.response_json["code"] == "QIT000002"

    def test_request_id_round_trip(self):
        client = ObjectGenerator.create_client()
        request_id = "qitech-request-001"
        response = ClientRequisition.send(
            "GET",
            f"/client/{client['client_key']}",
            headers={
                "INTERNAL-TOKEN": INTERNAL_TOKEN,
                "X-CLIENT-KEY": client["client_key"],
                "X-Request-ID": request_id,
            },
        )
        assert response.response_status == 200
        assert response.response.headers["X-Request-ID"] == request_id

    def test_unsafe_request_id_is_replaced(self):
        client = ObjectGenerator.create_client()
        unsafe_request_id = "x" * 65
        response = ClientRequisition.send(
            "GET",
            f"/client/{client['client_key']}",
            headers={
                "INTERNAL-TOKEN": INTERNAL_TOKEN,
                "X-CLIENT-KEY": client["client_key"],
                "X-Request-ID": unsafe_request_id,
            },
        )
        assert response.response_status == 200
        returned = response.response.headers["X-Request-ID"]
        assert returned != unsafe_request_id
        assert 1 <= len(returned) <= 64

    def test_public_responses_never_expose_internal_id(self):
        client, account = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(account["account_key"], client["client_key"], 12345)

        status, client_response = RequestGenerator.GET_client(
            client["client_key"], client["client_key"]
        )
        assert status == 200

        status, account_response = RequestGenerator.GET_account(
            account["account_key"], client["client_key"]
        )
        assert status == 200

        status, statement_response = RequestGenerator.GET_transactions(
            account["account_key"], client["client_key"]
        )
        assert status == 200

        assert_no_internal_id(client_response)
        assert_no_internal_id(account_response)
        assert_no_internal_id(statement_response)
