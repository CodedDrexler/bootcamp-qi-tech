from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import TransactionController
from utils.schema_handler import SchemaHandler


DEFAULT_LIMIT = 20
DEFAULT_PAGE = 0


class TransactionResource:
    @SchemaHandler.validate("post_transaction.json")
    def on_post(self, request: Request, account_key: str, payload: dict) -> JSONResponse:
        controller = TransactionController()
        transaction = controller.create(
            account_key=account_key,
            transaction_data=payload,
            requester_client_key=request.headers.get("X-CLIENT-KEY"),
        )
        return JSONResponse(
            content=jsonable_encoder(transaction),
            status_code=http_status.HTTP_201_CREATED,
        )

    @SchemaHandler.validate_query_params("get_account_transactions.json")
    def on_get_list(self, request: Request, account_key: str) -> JSONResponse:
        query_params = request.query_params
        limit = int(query_params.get("limit", DEFAULT_LIMIT))
        page = int(query_params.get("page", DEFAULT_PAGE))

        controller = TransactionController()
        result = controller.get_statement(
            account_key=account_key,
            requester_client_key=request.headers.get("X-CLIENT-KEY"),
            limit=limit,
            offset=page * limit,
        )

        return JSONResponse(
            content=jsonable_encoder(
                {
                    "data": result["transactions"],
                    "limit": limit,
                    "page": page,
                    "is_last_page": result["is_last_page"],
                }
            ),
            status_code=http_status.HTTP_200_OK,
        )
