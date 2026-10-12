from uuid import uuid4

from sqlalchemy import func, or_

from database import Context
from models import BankTransaction, TransactionType


class TransactionRepository:
    """Persistência append-only das movimentações financeiras."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_type(self, enumerator: str) -> TransactionType:
        return (
            self.session.query(TransactionType)
            .filter(TransactionType.enumerator == enumerator)
            .one()
        )

    def create_deposit(
        self,
        destination_account,
        amount: int,
        request_control_key: str,
        external_reference: str,
        operation_key: str | None = None,
    ) -> BankTransaction:
        transaction = BankTransaction()
        transaction.transaction_key = str(uuid4())
        transaction.operation_key = operation_key or str(uuid4())
        transaction.request_control_key = request_control_key
        transaction.external_reference = external_reference
        transaction.type = self.get_type(TransactionType.DEPOSIT)
        transaction.destination_account = destination_account
        transaction.amount = amount
        self.session.add(transaction)
        return transaction

    def create_transfer(
        self,
        origin_account,
        destination_account,
        amount: int,
        request_control_key: str,
        operation_key: str | None = None,
    ) -> BankTransaction:
        transaction = BankTransaction()
        transaction.transaction_key = str(uuid4())
        transaction.operation_key = operation_key or str(uuid4())
        transaction.request_control_key = request_control_key
        transaction.external_reference = None
        transaction.type = self.get_type(TransactionType.TRANSFER)
        transaction.origin_account = origin_account
        transaction.destination_account = destination_account
        transaction.amount = amount
        self.session.add(transaction)
        return transaction

    def create_fee(self, origin_account, amount: int, operation_key: str) -> BankTransaction:
        transaction = BankTransaction()
        transaction.transaction_key = str(uuid4())
        transaction.operation_key = operation_key
        transaction.request_control_key = None
        transaction.external_reference = None
        transaction.type = self.get_type(TransactionType.FEE)
        transaction.origin_account = origin_account
        transaction.amount = amount
        self.session.add(transaction)
        return transaction

    def create_piggy_movement(self, account, piggy, kind, amount, key):
        transaction = BankTransaction(transaction_key=str(uuid4()), operation_key=str(uuid4()),
            request_control_key=key, type=self.get_type(kind), amount=amount,
            piggy_bank=piggy, account_balance_after=account.balance,piggy_balance_after=piggy.balance)
        if kind == TransactionType.RESERVE:
            transaction.origin_account = account
        else:
            transaction.destination_account = account
        self.session.add(transaction)
        return transaction

    def get_by_request_control_key(self, request_control_key: str) -> BankTransaction:
        return (
            self.session.query(BankTransaction)
            .filter(BankTransaction.request_control_key == request_control_key)
            .first()
        )

    def get_by_external_reference(self, external_reference: str) -> BankTransaction:
        return (
            self.session.query(BankTransaction)
            .filter(BankTransaction.external_reference == external_reference)
            .first()
        )

    def get_fee_by_operation_key(self, operation_key: str) -> BankTransaction:
        return (
            self.session.query(BankTransaction)
            .join(BankTransaction.type)
            .filter(
                BankTransaction.operation_key == operation_key,
                TransactionType.enumerator == TransactionType.FEE,
            )
            .first()
        )

    def outgoing_transfer_amount_today(self, account_id: int) -> int:
        value = (
            self.session.query(func.coalesce(func.sum(BankTransaction.amount), 0))
            .join(BankTransaction.type)
            .filter(
                BankTransaction.origin_account_id == account_id,
                TransactionType.enumerator == TransactionType.TRANSFER,
                func.date(BankTransaction.created_at) == func.current_date(),
            )
            .scalar()
        )
        return int(value or 0)

    def list_page_for_account(self, account_id: int, limit: int, offset: int) -> list[BankTransaction]:
        query = (
            self.session.query(BankTransaction)
            .filter(
                or_(
                    BankTransaction.origin_account_id == account_id,
                    BankTransaction.destination_account_id == account_id,
                )
            )
            .order_by(BankTransaction.created_at.desc(), BankTransaction.id.desc())
        )
        return query.limit(limit + 1).offset(offset).all()
