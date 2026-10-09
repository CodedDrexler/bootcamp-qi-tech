from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from dtos import TransactionDTO
from errors import (
    AccountNotFound,
    InsufficientBalance,
    MissingClientIdentity,
    RequestControlKeyConflict,
    SameAccountTransfer,
)
from models import TransactionType
from repositories import AccountRepository, TransactionRepository


# Decisão de produto do MVP, inspirada no exemplo da Aula 2: R$ 2,00.
# A regra fica num único ponto e a tarifa também vira fato no extrato.
TRANSFER_FEE = 200


class TransactionController(BaseController):
    """Núcleo financeiro: saldo, tarifa, atomicidade, locks e idempotência."""

    def __init__(self) -> None:
        super().__init__(__name__)
        self.account_repository = AccountRepository(self.context)
        self.transaction_repository = TransactionRepository(self.context)

    def create(self, account_key: str, transaction_data: dict, requester_client_key: str | None) -> dict:
        self._require_identity(requester_client_key)

        transaction_type = transaction_data["type"]
        if transaction_type == TransactionType.DEPOSIT:
            return self._deposit(account_key, transaction_data, requester_client_key)

        return self._transfer(account_key, transaction_data, requester_client_key)

    def get_statement(
        self,
        account_key: str,
        requester_client_key: str | None,
        limit: int,
        offset: int,
    ) -> dict:
        self._require_identity(requester_client_key)

        account = self.account_repository.get_by_key(account_key)
        if account is None or account.client.client_key != requester_client_key:
            raise AccountNotFound(account_key)

        transactions = self.transaction_repository.list_page_for_account(account.id, limit, offset)

        is_last_page = True
        if len(transactions) > limit:
            is_last_page = False
            transactions = transactions[:-1]

        return {
            "transactions": TransactionDTO.statement_list(transactions, account.id),
            "is_last_page": is_last_page,
        }

    def _deposit(self, account_key: str, data: dict, requester_client_key: str) -> dict:
        request_control_key = data["request_control_key"]
        amount = data["amount"]

        accounts = self.account_repository.get_many_for_update([account_key])
        account_by_key = {account.account_key: account for account in accounts}
        account = account_by_key.get(account_key)

        if account is None or account.client.client_key != requester_client_key:
            raise AccountNotFound(account_key)

        # Rechecagem depois do lock: uma repetição concorrente pode ter
        # ficado esperando a primeira requisição terminar.
        replay = self._get_replay_if_matches(
            request_control_key=request_control_key,
            expected_type=TransactionType.DEPOSIT,
            expected_amount=amount,
            expected_origin_key=None,
            expected_destination_key=account_key,
        )
        if replay is not None:
            return replay

        self.account_repository.add_balance(account, amount)
        transaction = self.transaction_repository.create_deposit(
            destination_account=account,
            amount=amount,
            request_control_key=request_control_key,
        )

        return self._flush_commit_or_replay(
            transaction=transaction,
            fee_amount=0,
            request_control_key=request_control_key,
            expected_type=TransactionType.DEPOSIT,
            expected_amount=amount,
            expected_origin_key=None,
            expected_destination_key=account_key,
        )

    def _transfer(self, origin_account_key: str, data: dict, requester_client_key: str) -> dict:
        destination_account_key = data["destination_account_key"]
        request_control_key = data["request_control_key"]
        amount = data["amount"]

        if origin_account_key == destination_account_key:
            raise SameAccountTransfer()

        accounts = self.account_repository.get_many_for_update(
            [origin_account_key, destination_account_key]
        )
        account_by_key = {account.account_key: account for account in accounts}
        origin_account = account_by_key.get(origin_account_key)
        destination_account = account_by_key.get(destination_account_key)

        if origin_account is None or origin_account.client.client_key != requester_client_key:
            raise AccountNotFound(origin_account_key)

        if destination_account is None:
            raise AccountNotFound(destination_account_key)

        replay = self._get_replay_if_matches(
            request_control_key=request_control_key,
            expected_type=TransactionType.TRANSFER,
            expected_amount=amount,
            expected_origin_key=origin_account_key,
            expected_destination_key=destination_account_key,
        )
        if replay is not None:
            return replay

        required_amount = amount + TRANSFER_FEE
        if origin_account.balance < required_amount:
            raise InsufficientBalance(origin_account.balance, required_amount)

        self.account_repository.subtract_balance(origin_account, required_amount)
        self.account_repository.add_balance(destination_account, amount)

        transfer = self.transaction_repository.create_transfer(
            origin_account=origin_account,
            destination_account=destination_account,
            amount=amount,
            request_control_key=request_control_key,
        )
        self.transaction_repository.create_fee(
            origin_account=origin_account,
            amount=TRANSFER_FEE,
            operation_key=transfer.operation_key,
        )

        return self._flush_commit_or_replay(
            transaction=transfer,
            fee_amount=TRANSFER_FEE,
            request_control_key=request_control_key,
            expected_type=TransactionType.TRANSFER,
            expected_amount=amount,
            expected_origin_key=origin_account_key,
            expected_destination_key=destination_account_key,
        )

    def _get_replay_if_matches(
        self,
        request_control_key: str,
        expected_type: str,
        expected_amount: int,
        expected_origin_key: str | None,
        expected_destination_key: str | None,
    ) -> dict | None:
        existing = self.transaction_repository.get_by_request_control_key(request_control_key)
        if existing is None:
            return None

        origin_key = existing.origin_account.account_key if existing.origin_account is not None else None
        destination_key = (
            existing.destination_account.account_key
            if existing.destination_account is not None
            else None
        )

        same_request = (
            existing.type.enumerator == expected_type
            and existing.amount == expected_amount
            and origin_key == expected_origin_key
            and destination_key == expected_destination_key
        )

        if not same_request:
            raise RequestControlKeyConflict(request_control_key)

        fee = self.transaction_repository.get_fee_by_operation_key(existing.operation_key)
        fee_amount = fee.amount if fee is not None else 0
        return TransactionDTO.operation_to_dict(existing, fee_amount=fee_amount)

    def _flush_commit_or_replay(
        self,
        transaction,
        fee_amount: int,
        request_control_key: str,
        expected_type: str,
        expected_amount: int,
        expected_origin_key: str | None,
        expected_destination_key: str | None,
    ) -> dict:
        """Materializa constraints antes do commit e resolve retry concorrente.

        Se outra requisição conseguiu usar a mesma request_control_key em
        contas diferentes enquanto esta trabalhava, o UNIQUE do banco é a
        última linha de defesa. O rollback desfaz também qualquer saldo
        alterado nesta tentativa; em seguida buscamos o vencedor e aplicamos
        a mesma regra de replay/conflito.
        """
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            replay = self._get_replay_if_matches(
                request_control_key=request_control_key,
                expected_type=expected_type,
                expected_amount=expected_amount,
                expected_origin_key=expected_origin_key,
                expected_destination_key=expected_destination_key,
            )
            if replay is not None:
                return replay
            raise

        response = TransactionDTO.operation_to_dict(transaction, fee_amount=fee_amount)
        self.session.commit()
        return response

    def _require_identity(self, requester_client_key: str | None) -> None:
        if requester_client_key is None or requester_client_key == "":
            raise MissingClientIdentity()
