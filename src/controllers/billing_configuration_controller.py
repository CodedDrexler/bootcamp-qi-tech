from controllers.base_controller import BaseController
from dtos import BillingConfigurationDTO
from models import BillingConfiguration
from repositories import BillingConfigurationRepository


class BillingConfigurationController(BaseController):
    """Política comercial interna; clientes finais não escolhem a própria tarifa."""

    def __init__(self) -> None:
        super().__init__(__name__)
        self.billing_repository = BillingConfigurationRepository(self.context)

    def get_transfer_policy(self) -> dict:
        return BillingConfigurationDTO.obj_to_dict(self.billing_repository.get_transfer_policy())

    def update_transfer_policy(self, payload: dict) -> dict:
        expense_type = payload["expense_type"]
        policy = self.billing_repository.update_transfer_policy(
            expense_type=expense_type,
            amount=payload.get("amount") if expense_type == BillingConfiguration.FIXED_AMOUNT else None,
            percentage_basis_points=(
                payload.get("percentage_basis_points")
                if expense_type == BillingConfiguration.PERCENTAGE
                else None
            ),
        )
        self.session.flush()
        response = BillingConfigurationDTO.obj_to_dict(policy)
        self.session.commit()
        return response
