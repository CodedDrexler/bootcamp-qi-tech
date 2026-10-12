class PiggyBankDTO:
    @staticmethod
    def obj_to_dict(piggy, account_key):
        return {
            "piggy_bank_key": piggy.piggy_bank_key,
            "account_key": account_key,
            "name": piggy.name,
            "description": piggy.description,
            "target_amount": piggy.target_amount,
            "target_date": piggy.target_date.isoformat() if piggy.target_date else None,
            "balance": piggy.balance,
            "status": piggy.status,
            "version": piggy.version,
            "currency": "BRL",
            "goal_reached": piggy.balance >= piggy.target_amount,
            "progress_basis_points": min(
                10000, piggy.balance * 10000 // piggy.target_amount
            ),
            "remaining_amount": max(0, piggy.target_amount - piggy.balance),
            "created_at": piggy.created_at.isoformat(),
            "updated_at": piggy.updated_at.isoformat(),
        }

    @staticmethod
    def event_to_dict(event):
        return {
            "event_key": event.event_key,
            "type": event.type,
            "version": event.version,
            "changes": event.changes,
            "created_at": event.created_at.isoformat(),
        }

    @staticmethod
    def operation_to_dict(transaction):
        account = transaction.origin_account or transaction.destination_account
        return {
            "transaction_key": transaction.transaction_key,
            "operation_key": transaction.operation_key,
            "request_control_key": transaction.request_control_key,
            "type": transaction.type.enumerator,
            "account_key": account.account_key,
            "piggy_bank_key": transaction.piggy_bank.piggy_bank_key,
            "amount": transaction.amount,
            "fee_amount": 0,
            "balance_after": transaction.piggy_balance_after,
            "available_balance_after": transaction.account_balance_after,
            "created_at": transaction.created_at.isoformat(),
        }

    @staticmethod
    def statement_item(transaction):
        data = PiggyBankDTO.operation_to_dict(transaction)
        data["balance_effect"] = (
            transaction.amount
            if transaction.type.enumerator == "reserve"
            else -transaction.amount
        )
        data["currency"] = "BRL"
        return data


def page_envelope(objects, limit, page, convert):
    return {
        "data": [convert(obj) for obj in objects[:limit]],
        "limit": limit,
        "page": page,
        "is_last_page": len(objects) <= limit,
    }
