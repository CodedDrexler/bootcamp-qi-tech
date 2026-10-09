from os import environ

from tests.utils.requisition import ClientRequisition, BaseConnectorResponse


INTERNAL_TOKEN = environ.get("INTERNAL_TOKEN", "default_token")


class RequestGenerator:
    @staticmethod
    def POST_sample_entity(sample_entity_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST",
            "/sample_entity",
            payload=sample_entity_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )

        return response.response_status, response.response_json

    @staticmethod
    def GET_sample_entity(sample_entity_key: str) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET",
            f"/sample_entity/{sample_entity_key}",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def PUT_sample_entity(sample_entity_key: str, update_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "PUT",
            f"/sample_entity/{sample_entity_key}",
            payload=update_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def PUT_webhook_sample_entity(sample_entity_key: str) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "PUT",
            f"/webhook/sample_entity/{sample_entity_key}/increment_counter",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_sample_entities(params: dict = None) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET", "/sample_entities", headers={"INTERNAL-TOKEN": INTERNAL_TOKEN}, query_params=params
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_client(client_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST",
            "/client",
            payload=client_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_client(client_key: str, requester_client_key: str = None) -> BaseConnectorResponse:
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if requester_client_key is not None:
            headers["X-CLIENT-KEY"] = requester_client_key
        response = ClientRequisition.send(
            "GET",
            f"/client/{client_key}",
            headers=headers,
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_account(client_key: str, requester_client_key: str = None) -> BaseConnectorResponse:
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if requester_client_key is not None:
            headers["X-CLIENT-KEY"] = requester_client_key
        response = ClientRequisition.send(
            "POST",
            f"/client/{client_key}/account",
            headers=headers,
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_account(account_key: str, requester_client_key: str = None) -> BaseConnectorResponse:
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if requester_client_key is not None:
            headers["X-CLIENT-KEY"] = requester_client_key
        response = ClientRequisition.send(
            "GET",
            f"/account/{account_key}",
            headers=headers,
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_transaction(
        account_key: str,
        transaction_payload: dict,
        requester_client_key: str = None,
    ) -> BaseConnectorResponse:
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if requester_client_key is not None:
            headers["X-CLIENT-KEY"] = requester_client_key
        response = ClientRequisition.send(
            "POST",
            f"/account/{account_key}/transaction",
            payload=transaction_payload,
            headers=headers,
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_transactions(
        account_key: str,
        requester_client_key: str = None,
        params: dict = None,
    ) -> BaseConnectorResponse:
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if requester_client_key is not None:
            headers["X-CLIENT-KEY"] = requester_client_key
        response = ClientRequisition.send(
            "GET",
            f"/account/{account_key}/transactions",
            headers=headers,
            query_params=params,
        )
        return response.response_status, response.response_json

