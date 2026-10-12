import re
from fastapi import Request
from fastapi.responses import JSONResponse
from controllers.bank_controller import BankController
from dtos.bank_dto import customer_dto
from errors.base_error import InvalidSchema
from utils.schema_handler import SchemaHandler


def pagination(request):
    values = dict(request.query_params)
    if set(values) - {"limit", "page"} or any(len(request.query_params.getlist(k)) > 1 for k in values):
        raise InvalidSchema("Only one limit and one page parameter are allowed.")
    limit, page = values.get("limit", "10"), values.get("page", "0")
    if not re.fullmatch(r"[0-9]{1,3}", limit) or not re.fullmatch(r"[0-9]{1,9}", page):
        raise InvalidSchema("limit and page must be nonnegative integers.")
    if not 1 <= int(limit) <= 100:
        raise InvalidSchema("limit must be between 1 and 100.")
    return int(limit), int(page)


def create(request, payload, scope, operation):
    key = request.headers.get("Idempotency-Key", "")
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", key):
        raise InvalidSchema("Idempotency-Key is required: 1-128 ASCII letters, digits, dot, colon, underscore or hyphen.")
    c = BankController()
    return JSONResponse(c.execute(scope, key, payload, lambda: operation(c)), status_code=201)


class BankResource:
    @SchemaHandler.validate("post_customer.json")
    def post_customer(self, request: Request, payload: dict):
        return create(request, payload, "/customers", lambda c: c.create_customer(payload))

    def get_customer(self, customer_key: str):
        c = BankController()
        return customer_dto(c.customer(customer_key))

    def customers(self, request: Request):
        return BankController().list_customers(*pagination(request))

    @SchemaHandler.validate("post_account.json")
    def post_account(self, request: Request, payload: dict):
        return create(request, payload, "/accounts", lambda c: c.create_account(payload))

    def get_account(self, account_key: str):
        return BankController().get_account(account_key)

    def accounts(self, request: Request):
        return BankController().list_accounts(*pagination(request))

    @SchemaHandler.validate("patch_close.json")
    def patch_account(self, account_key: str, payload: dict):
        return BankController().close_account(account_key)

    @SchemaHandler.validate("post_transaction.json")
    def post_transaction(self, account_key: str, request: Request, payload: dict):
        return create(request, payload, f"/accounts/{account_key}/transactions", lambda c: c.transact(account_key, payload))

    def transactions(self, account_key: str, request: Request):
        return BankController().statement(account_key, None, *pagination(request))

    @SchemaHandler.validate("post_piggy_bank.json")
    def post_piggy(self, account_key: str, request: Request, payload: dict):
        return create(request, payload, f"/accounts/{account_key}/piggy_banks", lambda c: c.create_piggy(account_key, payload))

    def piggies(self, account_key: str, request: Request):
        return BankController().list_piggies(account_key, *pagination(request))

    def get_piggy(self, account_key: str, piggy_bank_key: str):
        return BankController().get_piggy(account_key, piggy_bank_key)

    @SchemaHandler.validate("patch_close.json")
    def patch_piggy(self, account_key: str, piggy_bank_key: str, payload: dict):
        return BankController().close_piggy(account_key, piggy_bank_key)

    @SchemaHandler.validate("post_piggy_transaction.json")
    def post_piggy_transaction(self, account_key: str, piggy_bank_key: str, request: Request, payload: dict):
        scope = f"/accounts/{account_key}/piggy_banks/{piggy_bank_key}/transactions"
        return create(request, payload, scope, lambda c: c.transact_piggy(account_key, piggy_bank_key, payload))

    def piggy_transactions(self, account_key: str, piggy_bank_key: str, request: Request):
        return BankController().statement(account_key, piggy_bank_key, *pagination(request))


def register_bank_routes(app):
    r = BankResource()
    routes = [
        ("/customers", "POST", r.post_customer), ("/customers", "GET", r.customers),
        ("/customers/{customer_key}", "GET", r.get_customer),
        ("/accounts", "POST", r.post_account), ("/accounts", "GET", r.accounts),
        ("/accounts/{account_key}", "GET", r.get_account), ("/accounts/{account_key}", "PATCH", r.patch_account),
        ("/accounts/{account_key}/transactions", "POST", r.post_transaction),
        ("/accounts/{account_key}/transactions", "GET", r.transactions),
        ("/accounts/{account_key}/piggy_banks", "POST", r.post_piggy),
        ("/accounts/{account_key}/piggy_banks", "GET", r.piggies),
        ("/accounts/{account_key}/piggy_banks/{piggy_bank_key}", "GET", r.get_piggy),
        ("/accounts/{account_key}/piggy_banks/{piggy_bank_key}", "PATCH", r.patch_piggy),
        ("/accounts/{account_key}/piggy_banks/{piggy_bank_key}/transactions", "POST", r.post_piggy_transaction),
        ("/accounts/{account_key}/piggy_banks/{piggy_bank_key}/transactions", "GET", r.piggy_transactions),
    ]
    for path, method, endpoint in routes:
        app.add_api_route(path, endpoint, methods=[method])
