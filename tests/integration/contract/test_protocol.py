from uuid import uuid4

from tests.utils import INTERNAL_TOKEN, ObjectGenerator, PayloadGenerator, RequestGenerator
from tests.utils.requisition import ClientRequisition


ERROR_FIELDS = {"title", "description", "translation", "code"}


def assert_qi_error(response, status: int, code: str):
    assert response.response_status == status
    assert set(response.response_json.keys()) == ERROR_FIELDS
    assert response.response_json["code"] == code
    assert response.response.headers.get("X-Request-ID")


class TestProtocolContract:
    def test_health_check_is_public_and_fast_contract_is_204(self):
        response = ClientRequisition.send("GET", "/health_check")
        assert response.response_status == 204
        assert response.response.headers.get("X-Request-ID")

    def test_unknown_route_with_valid_internal_token_returns_named_404(self):
        response = ClientRequisition.send(
            "GET",
            "/route-that-does-not-exist",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        assert_qi_error(response, 404, "QIT000404")

    def test_wrong_http_method_returns_named_405(self):
        response = ClientRequisition.send(
            "DELETE",
            "/client",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        assert_qi_error(response, 405, "QIT000405")

    def test_malformed_json_returns_qi_400_instead_of_framework_422(self):
        response = ClientRequisition.send(
            "POST",
            "/client",
            data='{"name": "Ana",',
            headers={
                "INTERNAL-TOKEN": INTERNAL_TOKEN,
                "Content-Type": "application/json",
            },
        )
        assert_qi_error(response, 400, "QIT000001")

    def test_every_banking_surface_requires_internal_token(self):
        client, account = ObjectGenerator.create_client_with_account()
        deposit = PayloadGenerator.create_deposit_payload(amount=100)

        calls = [
            ("POST", "/client", PayloadGenerator.create_client_payload(), None),
            ("GET", f"/client/{client['client_key']}", None, {"X-CLIENT-KEY": client["client_key"]}),
            ("POST", f"/client/{client['client_key']}/account", None, {"X-CLIENT-KEY": client["client_key"]}),
            ("GET", f"/account/{account['account_key']}", None, {"X-CLIENT-KEY": client["client_key"]}),
            ("PUT", f"/account/{account['account_key']}/limits", {"single_transfer_limit": 10000, "daily_transfer_limit": 20000}, None),
            ("PUT", f"/webhook/account/{account['account_key']}/status", {"status": "blocked"}, None),
            ("GET", "/billing_configuration/transfer", None, None),
            ("PUT", "/billing_configuration/transfer", {"expense_type": "fixed_amount", "amount": 200}, None),
            ("POST", f"/account/{account['account_key']}/transaction", deposit, {"X-CLIENT-KEY": client["client_key"]}),
            ("GET", f"/account/{account['account_key']}/transactions", None, {"X-CLIENT-KEY": client["client_key"]}),
        ]

        for method, endpoint, payload, headers in calls:
            response = ClientRequisition.send(method, endpoint, payload=payload, headers=headers or {})
            assert_qi_error(response, 403, "QIT000002")

    def test_request_id_is_returned_even_when_business_rule_rejects_request(self):
        client, account = ObjectGenerator.create_client_with_account()
        request_id = "business-error-correlation-001"
        payload = PayloadGenerator.create_transfer_payload(account["account_key"], amount=100)
        response = ClientRequisition.send(
            "POST",
            f"/account/{account['account_key']}/transaction",
            payload=payload,
            headers={
                "INTERNAL-TOKEN": INTERNAL_TOKEN,
                "X-CLIENT-KEY": client["client_key"],
                "X-Request-ID": request_id,
            },
        )
        assert response.response_status == 409
        assert response.response_json["code"] == "QIT004002"
        assert response.response.headers["X-Request-ID"] == request_id

    def test_error_payload_has_stable_machine_readable_shape(self):
        client = ObjectGenerator.create_client()
        unknown = "00000000-0000-4000-8000-000000000000"
        response = ClientRequisition.send(
            "GET",
            f"/account/{unknown}",
            headers={
                "INTERNAL-TOKEN": INTERNAL_TOKEN,
                "X-CLIENT-KEY": client["client_key"],
            },
        )
        assert_qi_error(response, 404, "QIT003001")

    def test_arbitrary_identity_string_does_not_grant_access(self):
        owner, account = ObjectGenerator.create_client_with_account()
        response = ClientRequisition.send(
            "GET",
            f"/account/{account['account_key']}",
            headers={
                "INTERNAL-TOKEN": INTERNAL_TOKEN,
                "X-CLIENT-KEY": str(uuid4()),
            },
        )
        assert_qi_error(response, 404, "QIT003001")
