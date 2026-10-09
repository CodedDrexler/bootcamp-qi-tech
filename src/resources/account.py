from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import AccountController


class AccountResource:
    def on_post(self, request: Request, client_key: str) -> JSONResponse:
        controller = AccountController()
        account = controller.create(
            client_key=client_key,
            requester_client_key=request.headers.get("X-CLIENT-KEY"),
        )
        return JSONResponse(
            content=jsonable_encoder(account),
            status_code=http_status.HTTP_201_CREATED,
        )

    def on_get_by_key(self, request: Request, account_key: str) -> JSONResponse:
        controller = AccountController()
        account = controller.get_by_key(
            account_key=account_key,
            requester_client_key=request.headers.get("X-CLIENT-KEY"),
        )
        return JSONResponse(
            content=jsonable_encoder(account),
            status_code=http_status.HTTP_200_OK,
        )
