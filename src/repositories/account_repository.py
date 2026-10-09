from uuid import uuid4

from database import Context
from models import Account


class AccountRepository:
    """Persistência de contas e locks usados pelas operações financeiras."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, client) -> Account:
        account = Account()
        account.account_key = str(uuid4())
        account.client = client
        account.balance = 0
        self.session.add(account)
        return account

    def get_by_key(self, account_key: str) -> Account:
        return self.session.query(Account).filter(Account.account_key == account_key).first()

    def get_many_for_update(self, account_keys: list[str]) -> list[Account]:
        """Trava as contas sempre na mesma ordem para reduzir risco de deadlock.

        O lock é pessimista e vive até commit/rollback da transação SQL atual.
        A regra de saldo NÃO mora aqui; o controller lê os objetos já travados
        e decide se a operação pode acontecer.
        """
        distinct_keys = sorted(set(account_keys))
        return (
            self.session.query(Account)
            .filter(Account.account_key.in_(distinct_keys))
            .order_by(Account.account_key.asc())
            .with_for_update()
            .all()
        )

    def add_balance(self, account: Account, amount: int) -> None:
        account.balance = account.balance + amount

    def subtract_balance(self, account: Account, amount: int) -> None:
        account.balance = account.balance - amount
