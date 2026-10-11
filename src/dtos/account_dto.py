from models import Account


class AccountDTO:
    @staticmethod
    def only_key(account: Account) -> dict:
        return {"account_key": account.account_key}

    @staticmethod
    def limits(account: Account) -> dict:
        return {
            "account_key": account.account_key,
            "single_transfer_limit": account.single_transfer_limit,
            "daily_transfer_limit": account.daily_transfer_limit,
        }

    @staticmethod
    def status(account: Account) -> dict:
        return {
            "account_key": account.account_key,
            "status": account.status.enumerator,
        }

    @staticmethod
    def obj_to_dict(account: Account) -> dict:
        return {
            "account_key": account.account_key,
            "client_key": account.client.client_key,
            "status": account.status.enumerator,
            "balance": account.balance,
            "single_transfer_limit": account.single_transfer_limit,
            "daily_transfer_limit": account.daily_transfer_limit,
            "created_at": account.created_at.isoformat() if account.created_at else None,
        }
