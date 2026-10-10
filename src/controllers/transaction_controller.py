from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from dtos import TransactionDTO
from errors import (
    AccountNotFound,
    AccountNotOperational,
    DailyTransferLimitExceeded,
    FundingReferenceConflict,
    InsufficientBalance,
    MissingClientIdentity,
    RequestControlKeyConflict,
    SameAccountTransfer,
    TransferLimitExceeded,
)
from models import AccountStatus, BillingConfiguration, TransactionType
from repositories import AccountRepository, BillingConfigurationRepository, TransactionRepository
from utils.structured_log import emit_event


class TransactionController(BaseController):
    """Núcleo financeiro: saldo, tarifa, limites, locks e idempotência."""

    def __init__(self) -> None:
        super().__init__(__name__)
        self.account_repository = AccountRepository(self.context)
        self.transaction_repository = TransactionRepository(self.context)
        self.billing_repository = BillingConfigurationRepository(self.context)

    def create(self, account_key: str, transaction_data: dict, requester_client_key: str | None) -> dict:
        self._require_identity(requester_client_key)
        if transaction_data["type"] == TransactionType.DEPOSIT:
            return self._deposit(account_key, transaction_data, requester_client_key)
        return self._transfer(account_key, transaction_data, requester_client_key)

    def get_statement(self, account_key: str, requester_client_key: str | None, limit: int, offset: int) -> dict:
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
        funding_reference = data["funding_reference"]
        amount = data["amount"]

        accounts = self.account_repository.get_many_for_update([account_key])
        account = {item.account_key: item for item in accounts}.get(account_key)
        if account is None or account.client.client_key != requester_client_key:
            raise AccountNotFound(account_key)

        replay = self._get_replay_if_matches(
            request_control_key=request_control_key,
            expected_type=TransactionType.DEPOSIT,
            expected_amount=amount,
            expected_origin_key=None,
            expected_destination_key=account_key,
            expected_external_reference=funding_reference,
        )
        if replay is not None:
            self._log_financial_result(TransactionType.DEPOSIT, amount, 0, "replayed", replay.get("operation_key"))
            return replay

        self._require_operational_account(account)

        if self.transaction_repository.get_by_external_reference(funding_reference) is not None:
            raise FundingReferenceConflict(funding_reference)

        self.account_repository.add_balance(account, amount)
        transaction = self.transaction_repository.create_deposit(
            destination_account=account,
            amount=amount,
            request_control_key=request_control_key,
            external_reference=funding_reference,
        )
        return self._flush_commit_or_replay(
            transaction=transaction,
            fee_amount=0,
            request_control_key=request_control_key,
            expected_type=TransactionType.DEPOSIT,
            expected_amount=amount,
            expected_origin_key=None,
            expected_destination_key=account_key,
            expected_external_reference=funding_reference,
        )

    def _transfer(self, origin_account_key: str, data: dict, requester_client_key: str) -> dict:
        destination_account_key = data["destination_account_key"]
        request_control_key = data["request_control_key"]
        amount = data["amount"]

        if origin_account_key == destination_account_key:
            self._log_rejection(TransactionType.TRANSFER, amount, 0, "QIT004002")
            raise SameAccountTransfer()

        accounts = self.account_repository.get_many_for_update([origin_account_key, destination_account_key])
        by_key = {account.account_key: account for account in accounts}
        origin_account = by_key.get(origin_account_key)
        destination_account = by_key.get(destination_account_key)

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
            expected_external_reference=None,
        )
        if replay is not None:
            self._log_financial_result(
                TransactionType.TRANSFER, amount, replay.get("fee_amount", 0), "replayed", replay.get("operation_key")
            )
            return replay

        self._require_operational_account(origin_account)
        self._require_operational_account(destination_account)
        fee_amount = self._calculate_transfer_fee(amount)

        if amount > origin_account.single_transfer_limit:
            self._log_rejection(TransactionType.TRANSFER, amount, fee_amount, "QIT004004")
            raise TransferLimitExceeded(amount, origin_account.single_transfer_limit)

        amount_today = self.transaction_repository.outgoing_transfer_amount_today(origin_account.id)
        if amount_today + amount > origin_account.daily_transfer_limit:
            self._log_rejection(TransactionType.TRANSFER, amount, fee_amount, "QIT004005")
            raise DailyTransferLimitExceeded(amount_today, amount, origin_account.daily_transfer_limit)

        required_amount = amount + fee_amount
        if origin_account.balance < required_amount:
            self._log_rejection(TransactionType.TRANSFER, amount, fee_amount, "QIT004001")
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
            amount=fee_amount,
            operation_key=transfer.operation_key,
        )
        return self._flush_commit_or_replay(
            transaction=transfer,
            fee_amount=fee_amount,
            request_control_key=request_control_key,
            expected_type=TransactionType.TRANSFER,
            expected_amount=amount,
            expected_origin_key=origin_account_key,
            expected_destination_key=destination_account_key,
            expected_external_reference=None,
        )

    def _calculate_transfer_fee(self, amount: int) -> int:
        policy = self.billing_repository.get_transfer_policy()
        if policy.expense_type == BillingConfiguration.FIXED_AMOUNT:
            return int(policy.fixed_amount_cents)

        # Percentual em basis points evita float: 150 bps = 1,50%.
        # +5000 antes da divisão inteira implementa arredondamento half-up.
        calculated = (amount * int(policy.percentage_basis_points) + 5000) // 10000
        return max(1, calculated)

    def _require_operational_account(self, account) -> None:
        status = account.status.enumerator
        if status != AccountStatus.ACTIVE:
            raise AccountNotOperational(account.account_key, status)

    def _get_replay_if_matches(
        self,
        request_control_key: str,
        expected_type: str,
        expected_amount: int,
        expected_origin_key: str | None,
        expected_destination_key: str | None,
        expected_external_reference: str | None,
    ) -> dict | None:
        existing = self.transaction_repository.get_by_request_control_key(request_control_key)
        if existing is None:
            return None

        origin_key = existing.origin_account.account_key if existing.origin_account is not None else None
        destination_key = existing.destination_account.account_key if existing.destination_account is not None else None
        same_request = (
            existing.type.enumerator == expected_type
            and existing.amount == expected_amount
            and origin_key == expected_origin_key
            and destination_key == expected_destination_key
            and existing.external_reference == expected_external_reference
        )
        if not same_request:
            emit_event(
                "idempotency_conflict",
                result="rejected",
                error_code="QIT004003",
                operation_key=existing.operation_key,
            )
            raise RequestControlKeyConflict(request_control_key)

        fee = self.transaction_repository.get_fee_by_operation_key(existing.operation_key)
        return TransactionDTO.operation_to_dict(existing, fee_amount=fee.amount if fee is not None else 0)

    def _flush_commit_or_replay(
        self,
        transaction,
        fee_amount: int,
        request_control_key: str,
        expected_type: str,
        expected_amount: int,
        expected_origin_key: str | None,
        expected_destination_key: str | None,
        expected_external_reference: str | None,
    ) -> dict:
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            replay = self._get_replay_if_matches(
                request_control_key, expected_type, expected_amount,
                expected_origin_key, expected_destination_key, expected_external_reference,
            )
            if replay is not None:
                self._log_financial_result(
                    expected_type, expected_amount, replay.get("fee_amount", 0), "replayed", replay.get("operation_key")
                )
                return replay
            if expected_external_reference is not None:
                if self.transaction_repository.get_by_external_reference(expected_external_reference) is not None:
                    raise FundingReferenceConflict(expected_external_reference)
            raise

        response = TransactionDTO.operation_to_dict(transaction, fee_amount=fee_amount)
        self.session.commit()
        self._log_financial_result(
            expected_type, expected_amount, fee_amount, "committed", response.get("operation_key")
        )
        return response

    def _log_rejection(self, operation_type: str, amount: int, fee_amount: int, error_code: str) -> None:
        emit_event(
            "financial_operation", operation_type=operation_type, amount=amount, fee=fee_amount,
            result="rejected", error_code=error_code,
        )

    def _log_financial_result(
        self, operation_type: str, amount: int, fee_amount: int, result: str, operation_key: str | None
    ) -> None:
        emit_event(
            "financial_operation", operation_type=operation_type, amount=amount, fee=fee_amount,
            result=result, operation_key=operation_key,
        )

    def _require_identity(self, requester_client_key: str | None) -> None:
        if requester_client_key is None or requester_client_key == "":
            raise MissingClientIdentity()
