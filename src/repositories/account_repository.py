from uuid import uuid4

from database import Context
from constants import DEFAULT_DAILY_TRANSFER_LIMIT_CENTS, DEFAULT_SINGLE_TRANSFER_LIMIT_CENTS
from models import Account, AccountStatus, AccountStatusEvent


class AccountRepository:
    """Persistência de contas, limites e locks das operações financeiras."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, client) -> Account:
        account = Account()
        account.account_key = str(uuid4())
        account.client = client
        account.status = self.get_status(AccountStatus.ACTIVE)
        account.balance = 0
        account.single_transfer_limit = DEFAULT_SINGLE_TRANSFER_LIMIT_CENTS
        account.daily_transfer_limit = DEFAULT_DAILY_TRANSFER_LIMIT_CENTS
        self.session.add(account)
        self._create_status_event(account)
        return account

    def get_status(self, enumerator: str) -> AccountStatus:
        return (
            self.session.query(AccountStatus)
            .filter(AccountStatus.enumerator == enumerator)
            .one()
        )

    def update_status(self, account: Account, new_status: str) -> None:
        account.status = self.get_status(new_status)
        self._create_status_event(account)

    def update_limits(self, account: Account, single_transfer_limit: int, daily_transfer_limit: int) -> None:
        account.single_transfer_limit = single_transfer_limit
        account.daily_transfer_limit = daily_transfer_limit

    def _create_status_event(self, account: Account) -> None:
        event = AccountStatusEvent()
        event.account = account
        event.status = account.status
        self.session.add(event)

    def get_by_key(self, account_key: str) -> Account:
        return self.session.query(Account).filter(Account.account_key == account_key).first()

    def get_by_client_id(self, client_id: int) -> Account:
        return self.session.query(Account).filter(Account.client_id == client_id).first()

    def get_many_for_update(self, account_keys: list[str]) -> list[Account]:
        """Trava as contas sempre na mesma ordem para reduzir risco de deadlock."""
        distinct_keys = sorted(set(account_keys))
        return (
            self.session.query(Account)
            .filter(Account.account_key.in_(distinct_keys))
            .order_by(Account.account_key.asc())
            .with_for_update()
            .populate_existing()
            .all()
        )

    def add_balance(self, account: Account, amount: int) -> None:
        account.balance = account.balance + amount

    def subtract_balance(self, account: Account, amount: int) -> None:
        account.balance = account.balance - amount
