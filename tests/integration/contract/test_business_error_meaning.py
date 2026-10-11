from uuid import uuid4

from tests.utils import ObjectGenerator, PayloadGenerator, RequestGenerator


REQUIRED_ERROR_FIELDS = {"title", "description", "translation", "code"}


def assert_meaningful_error(status, body, expected_status, expected_code, expected_text):
    assert status == expected_status
    assert set(body) == REQUIRED_ERROR_FIELDS
    assert body["code"] == expected_code
    assert isinstance(body["title"], str) and body["title"].strip()
    assert isinstance(body["description"], str) and body["description"].strip()
    assert isinstance(body["translation"], str) and body["translation"].strip()
    assert expected_text.lower() in body["translation"].lower()


class TestBusinessErrorMeaning:
    def test_duplicate_name_is_not_a_business_error(self):
        """Nome nao identifica uma pessoa; CPF identifica o cadastro neste MVP."""
        first = PayloadGenerator.create_client_payload(name="Maria da Silva")
        second = PayloadGenerator.create_client_payload(name="Maria da Silva")

        status_a, body_a = RequestGenerator.POST_client(first)
        status_b, body_b = RequestGenerator.POST_client(second)

        assert status_a == 201
        assert status_b == 201
        assert body_a["client_key"] != body_b["client_key"]

    def test_duplicate_cpf_explains_the_conflict_to_the_client(self):
        payload = PayloadGenerator.create_client_payload()
        status, _ = RequestGenerator.POST_client(payload)
        assert status == 201

        status, body = RequestGenerator.POST_client(payload)
        assert_meaningful_error(status, body, 409, "QIT002003", "CPF")

    def test_second_account_explains_the_product_rule(self):
        client, _ = ObjectGenerator.create_client_with_account()
        status, body = RequestGenerator.POST_account(
            client["client_key"], requester_client_key=client["client_key"]
        )
        assert_meaningful_error(status, body, 409, "QIT003002", "já possui")

    def test_insufficient_balance_explains_amount_plus_fee_requirement(self):
        owner, origin = ObjectGenerator.create_client_with_account()
        _, destination = ObjectGenerator.create_client_with_account()
        payload = PayloadGenerator.create_transfer_payload(
            destination["account_key"], amount=1000
        )
        status, body = RequestGenerator.POST_transaction(
            origin["account_key"], payload, owner["client_key"]
        )
        assert_meaningful_error(status, body, 422, "QIT004001", "Saldo insuficiente")

    def test_same_account_transfer_explains_why_it_is_rejected(self):
        owner, account = ObjectGenerator.create_client_with_account()
        payload = PayloadGenerator.create_transfer_payload(
            account["account_key"], amount=100
        )
        status, body = RequestGenerator.POST_transaction(
            account["account_key"], payload, owner["client_key"]
        )
        assert_meaningful_error(status, body, 409, "QIT004002", "diferentes")

    def test_idempotency_conflict_explains_key_reuse(self):
        owner, origin = ObjectGenerator.create_client_with_account()
        _, destination = ObjectGenerator.create_client_with_account()
        ObjectGenerator.deposit(origin["account_key"], owner["client_key"], 5000)
        key = str(uuid4())

        first = PayloadGenerator.create_transfer_payload(
            destination["account_key"], amount=1000, request_control_key=key
        )
        status, _ = RequestGenerator.POST_transaction(
            origin["account_key"], first, owner["client_key"]
        )
        assert status == 201

        changed = PayloadGenerator.create_transfer_payload(
            destination["account_key"], amount=1200, request_control_key=key
        )
        status, body = RequestGenerator.POST_transaction(
            origin["account_key"], changed, owner["client_key"]
        )
        assert_meaningful_error(status, body, 409, "QIT004003", "idempotência")
