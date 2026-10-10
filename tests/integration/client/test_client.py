from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from tests.utils import DbUtils, ObjectGenerator, PayloadGenerator, RequestGenerator


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


    def test_exactly_eighteen_years_old_is_accepted(self):
        today = date.today()
        try:
            birthday = today.replace(year=today.year - 18)
        except ValueError:
            birthday = today.replace(year=today.year - 18, day=28)

        payload = PayloadGenerator.create_client_payload(birth_date=birthday.isoformat())
        status, _ = RequestGenerator.POST_client(payload)
        assert status == 201

    def test_client_still_under_eighteen_near_boundary_is_rejected(self):
        today = date.today()
        try:
            eighteenth_birthday = today.replace(year=today.year - 18)
        except ValueError:
            eighteenth_birthday = today.replace(year=today.year - 18, day=28)
        # O runner Windows e a API Linux podem estar em datas diferentes perto
        # da meia-noite. Uma margem de 7 dias preserva a regra que queremos
        # provar sem acoplar o teste ao fuso horario da maquina.
        birth_date = eighteenth_birthday + timedelta(days=7)

        payload = PayloadGenerator.create_client_payload(birth_date=birth_date.isoformat())
        status, response = RequestGenerator.POST_client(payload)
        assert status == 422
        assert response["code"] == "QIT002005"

    def test_future_birth_date_has_specific_business_error(self):
        # Mesmo motivo: nao usar +1 dia em teste black-box entre processos
        # que podem estar em fusos diferentes.
        future = date.today() + timedelta(days=7)
        payload = PayloadGenerator.create_client_payload(birth_date=future.isoformat())
        status, response = RequestGenerator.POST_client(payload)
        assert status == 422
        assert response["code"] == "QIT002006"

    def test_unknown_client_returns_404(self):
        unknown = "00000000-0000-4000-8000-000000000000"
        status, response = RequestGenerator.GET_client(unknown, unknown)
        assert status == 404
        assert response["code"] == "QIT002001"

    def test_two_concurrent_creates_with_same_cpf_create_only_one_client(self):
        DbUtils.rollback()
        payload = PayloadGenerator.create_client_payload()

        def create(_):
            return RequestGenerator.POST_client(payload)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(create, [0, 1]))

        statuses = sorted(status for status, _ in results)
        assert statuses == [201, 409]
        duplicate = next(body for status, body in results if status == 409)
        assert duplicate["code"] == "QIT002003"
