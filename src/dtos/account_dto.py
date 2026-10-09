from models import Account


class AccountDTO:
    @staticmethod
    def only_key(account: Account) -> dict:
        return {"account_key": account.account_key}

    @staticmethod
    def obj_to_dict(account: Account) -> dict:
        return {
            "account_key": account.account_key,
            "client_key": account.client.client_key,
            "balance": account.balance,
            "created_at": account.created_at.isoformat() if account.created_at else None,
        }
