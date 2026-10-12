from database import Context
from models import BillingConfiguration


class BillingConfigurationRepository:
    """Persistência da política comercial de tarifa do produto."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_transfer_policy(self, for_update: bool = False) -> BillingConfiguration:
        query = (
            self.session.query(BillingConfiguration)
            .filter(BillingConfiguration.operation_type == BillingConfiguration.TRANSFER)
        )
        if for_update:
            query = query.with_for_update()
        return query.one()

    def update_transfer_policy(self, expense_type: str, amount: int | None, percentage_basis_points: int | None):
        policy = self.get_transfer_policy(for_update=True)
        policy.expense_type = expense_type
        if expense_type == BillingConfiguration.FIXED_AMOUNT:
            policy.fixed_amount_cents = amount
            policy.percentage_basis_points = None
        else:
            policy.fixed_amount_cents = None
            policy.percentage_basis_points = percentage_basis_points
        return policy
