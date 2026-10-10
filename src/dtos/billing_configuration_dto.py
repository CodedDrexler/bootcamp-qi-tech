from models import BillingConfiguration


class BillingConfigurationDTO:
    @staticmethod
    def obj_to_dict(policy: BillingConfiguration) -> dict:
        response = {
            "operation_type": policy.operation_type,
            "expense_type": policy.expense_type,
        }
        if policy.expense_type == BillingConfiguration.FIXED_AMOUNT:
            response["amount"] = policy.fixed_amount_cents
        else:
            response["percentage_basis_points"] = policy.percentage_basis_points
        return response
