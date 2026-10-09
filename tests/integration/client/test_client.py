from datetime import date

from tests.utils import ObjectGenerator, PayloadGenerator, RequestGenerator


def birth_date_for_age(age: int) -> str:
    today = date.today()
    return f"{today.year - age:04d}-{today.month:02d}-{today.day:02d}"


class TestClient:
    def test_create_and_get_client(self):
        payload = PayloadGenerator.create_client_payload()
        status, response = RequestGenerator.POST_client(payload)
        assert status == 201
        client_key = response["client_key"]

        status, response = RequestGenerator.GET_client(client_key, client_key)
        assert status == 200
        assert response["client_key"] == client_key
        assert response["name"] == payload["name"]
        assert response["document_number"] == payload["document_number"]
        assert response["birth_date"] == payload["birth_date"]
        assert "id" not in response

    def test_schema_refuses_missing_required_field(self):
        payload = PayloadGenerator.create_client_payload()
        del payload["document_number"]
        status, response = RequestGenerator.POST_client(payload)
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_schema_refuses_extra_field(self):
        payload = PayloadGenerator.create_client_payload()
        payload["admin"] = True
        status, response = RequestGenerator.POST_client(payload)
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_schema_refuses_malformed_document_number(self):
        payload = PayloadGenerator.create_client_payload(document_number="12345678901")
        status, response = RequestGenerator.POST_client(payload)
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_refuses_mathematically_invalid_cpf(self):
        payload = PayloadGenerator.create_client_payload(document_number="111.222.333-44")
        status, response = RequestGenerator.POST_client(payload)
        assert status == 422
        assert response["code"] == "QIT002002"

    def test_refuses_duplicated_document_number(self):
        first = PayloadGenerator.create_client_payload()
        status, _ = RequestGenerator.POST_client(first)
        assert status == 201

        second = PayloadGenerator.create_client_payload(document_number=first["document_number"])
        status, response = RequestGenerator.POST_client(second)
        assert status == 409
        assert response["code"] == "QIT002003"

    def test_refuses_impossible_birth_date(self):
        payload = PayloadGenerator.create_client_payload(birth_date="2026-02-30")
        status, response = RequestGenerator.POST_client(payload)
        assert status == 422
        assert response["code"] == "QIT002004"

    def test_refuses_underage_client(self):
        payload = PayloadGenerator.create_client_payload(birth_date=birth_date_for_age(17))
        status, response = RequestGenerator.POST_client(payload)
        assert status == 422
        assert response["code"] == "QIT002005"

    def test_get_requires_client_identity(self):
        client = ObjectGenerator.create_client()
        status, response = RequestGenerator.GET_client(client["client_key"])
        assert status == 401
        assert response["code"] == "QIT005001"

    def test_client_cannot_read_another_client(self):
        first = ObjectGenerator.create_client()
        second = ObjectGenerator.create_client()
        status, response = RequestGenerator.GET_client(
            first["client_key"], requester_client_key=second["client_key"]
        )
        assert status == 404
        assert response["code"] == "QIT002001"
