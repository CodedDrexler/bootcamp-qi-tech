from tests.utils.requisition import BaseConnectorResponse
from tests.utils.payload_generator import PayloadGenerator
from tests.utils.request_generator import RequestGenerator


class ObjectGenerator:
    @staticmethod
    def create_sample_entity(hello: str = None) -> BaseConnectorResponse:

        sample_entity_payload = PayloadGenerator.create_sample_entity_payload(hello=hello)

        status, response = RequestGenerator.POST_sample_entity(sample_entity_payload)
        assert status == 201

        return response

    @staticmethod
    def update_sample_entity(sample_entity_key, new_status: str = None) -> BaseConnectorResponse:

        sample_entity_payload = PayloadGenerator.create_new_status_payload(new_status)

        status, response = RequestGenerator.PUT_sample_entity(sample_entity_key, sample_entity_payload)
        assert status == 202

        return response

    @staticmethod
    def create_client() -> dict:
        payload = PayloadGenerator.create_client_payload()
        status, response = RequestGenerator.POST_client(payload)
        assert status == 201
        return response

    @staticmethod
    def create_account(client_key: str) -> dict:
        status, response = RequestGenerator.POST_account(
            client_key=client_key,
            requester_client_key=client_key,
        )
        assert status == 201
        return response

    @staticmethod
    def create_client_with_account() -> tuple[dict, dict]:
        client = ObjectGenerator.create_client()
        account = ObjectGenerator.create_account(client["client_key"])
        return client, account

    @staticmethod
    def deposit(account_key: str, client_key: str, amount: int = 50000) -> dict:
        payload = PayloadGenerator.create_deposit_payload(amount=amount)
        status, response = RequestGenerator.POST_transaction(
            account_key,
            payload,
            requester_client_key=client_key,
        )
        assert status == 201
        return response

