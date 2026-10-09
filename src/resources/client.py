from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import ClientController
from utils.schema_handler import SchemaHandler


class ClientResource:
    @SchemaHandler.validate("post_client.json")
    def on_post(self, payload: dict) -> JSONResponse:
        controller = ClientController()
        client = controller.create(payload)
        return JSONResponse(
            content=jsonable_encoder(client),
            status_code=http_status.HTTP_201_CREATED,
        )

    def on_get_by_key(self, request: Request, client_key: str) -> JSONResponse:
        controller = ClientController()
        client = controller.get_by_key(
            client_key=client_key,
            requester_client_key=request.headers.get("X-CLIENT-KEY"),
        )
        return JSONResponse(
            content=jsonable_encoder(client),
            status_code=http_status.HTTP_200_OK,
        )
