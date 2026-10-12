from fastapi import Request
from fastapi.responses import JSONResponse
from controllers.piggy_bank_controller import PiggyBankController
from controllers.transaction_controller import TransactionController
from utils.schema_handler import SchemaHandler


def pagination(request):
    return int(request.query_params.get("limit", 20)), int(
        request.query_params.get("page", 0)
    )


class PiggyBankResource:
    @SchemaHandler.validate("post_piggy_bank.json")
    def post(self, request: Request, account_key: str, payload: dict):
        return JSONResponse(
            PiggyBankController().create(
                account_key, request.headers.get("X-CLIENT-KEY"), payload
            ),
            status_code=201,
        )

    def get(self, request: Request, account_key: str, piggy_bank_key: str):
        return PiggyBankController().get(
            account_key, request.headers.get("X-CLIENT-KEY"), piggy_bank_key
        )

    @SchemaHandler.validate_query_params("get_piggy_banks.json")
    def list(self, request: Request, account_key: str):
        return PiggyBankController().list(
            account_key,
            request.headers.get("X-CLIENT-KEY"),
            *pagination(request),
            request.query_params.get("status"),
        )

    @SchemaHandler.validate("patch_piggy_bank.json")
    def patch(
        self, request: Request, account_key: str, piggy_bank_key: str, payload: dict
    ):
        return PiggyBankController().update(
            account_key, request.headers.get("X-CLIENT-KEY"), piggy_bank_key, payload
        )

    @SchemaHandler.validate("put_piggy_bank_status.json")
    def close(
        self, request: Request, account_key: str, piggy_bank_key: str, payload: dict
    ):
        return PiggyBankController().close(
            account_key,
            request.headers.get("X-CLIENT-KEY"),
            piggy_bank_key,
            payload["expected_version"],
        )

    @SchemaHandler.validate("post_piggy_bank_transaction.json")
    def post_transaction(
        self, request: Request, account_key: str, piggy_bank_key: str, payload: dict
    ):
        return JSONResponse(
            TransactionController().create_piggy_movement(
                account_key,
                piggy_bank_key,
                payload,
                request.headers.get("X-CLIENT-KEY"),
            ),
            status_code=201,
        )

    @SchemaHandler.validate_query_params("get_account_transactions.json")
    def transactions(self, request: Request, account_key: str, piggy_bank_key: str):
        return PiggyBankController().transactions(
            account_key,
            request.headers.get("X-CLIENT-KEY"),
            piggy_bank_key,
            *pagination(request),
        )

    @SchemaHandler.validate_query_params("get_account_transactions.json")
    def events(self, request: Request, account_key: str, piggy_bank_key: str):
        return PiggyBankController().events(
            account_key,
            request.headers.get("X-CLIENT-KEY"),
            piggy_bank_key,
            *pagination(request),
        )

    def balances(self, request: Request, account_key: str):
        return PiggyBankController().balances(
            account_key, request.headers.get("X-CLIENT-KEY")
        )


def register_piggy_bank_routes(app):
    r = PiggyBankResource()
    root = "/account/{account_key}"
    item = root + "/piggy_bank/{piggy_bank_key}"
    for route, method, endpoint in [
        (root + "/piggy_bank", "POST", r.post),
        (root + "/piggy_banks", "GET", r.list),
        (item, "GET", r.get),
        (item, "PATCH", r.patch),
        (item + "/status", "PUT", r.close),
        (item + "/transaction", "POST", r.post_transaction),
        (item + "/transactions", "GET", r.transactions),
        (item + "/events", "GET", r.events),
        (root + "/balances", "GET", r.balances),
    ]:
        app.add_api_route(route, endpoint, methods=[method])
