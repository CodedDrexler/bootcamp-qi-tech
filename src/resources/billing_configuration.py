from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import BillingConfigurationController
from utils.schema_handler import SchemaHandler


class BillingConfigurationResource:
    def on_get_transfer(self) -> JSONResponse:
        controller = BillingConfigurationController()
        policy = controller.get_transfer_policy()
        return JSONResponse(content=jsonable_encoder(policy), status_code=http_status.HTTP_200_OK)

    @SchemaHandler.validate("put_transfer_billing_configuration.json")
    def on_put_transfer(self, payload: dict) -> JSONResponse:
        controller = BillingConfigurationController()
        policy = controller.update_transfer_policy(payload)
        return JSONResponse(content=jsonable_encoder(policy), status_code=http_status.HTTP_200_OK)
