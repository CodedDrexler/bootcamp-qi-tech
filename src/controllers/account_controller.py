from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from dtos import AccountDTO
from errors import (
    AccountAlreadyExists,
    AccountFinalStatus,
    AccountMustHaveZeroBalanceToClose,
    AccountNotFound,
    ClientNotFound,
    InvalidAccountLimits,
    MissingClientIdentity,
)
from models import AccountStatus
from repositories import AccountRepository, ClientRepository
from utils.identifiers import canonical_uuid
from repositories.piggy_bank_repository import PiggyBankRepository


class AccountController(BaseController):
    """Criação, consulta e configuração operacional de contas."""

    def __init__(self) -> None:
        super().__init__(__name__)
        self.client_repository = ClientRepository(self.context)
        self.account_repository = AccountRepository(self.context)
        self.piggy_repository = PiggyBankRepository(self.context)

    def create(self, client_key: str, requester_client_key: str | None) -> dict:
        client_key, requester_client_key = canonical_uuid(client_key), canonical_uuid(requester_client_key)
        self._require_identity(requester_client_key)

        if requester_client_key != client_key:
            raise ClientNotFound(client_key)

        client = self.client_repository.get_by_key(client_key)
        if client is None:
            raise ClientNotFound(client_key)

        if self.account_repository.get_by_client_id(client.id) is not None:
            raise AccountAlreadyExists(client_key)

        account = self.account_repository.create(client)

        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            if self.account_repository.get_by_client_id(client.id) is not None:
                raise AccountAlreadyExists(client_key)
            raise

        account_dto = AccountDTO.only_key(account)
        self.session.commit()
        return account_dto

    def get_by_key(self, account_key: str, requester_client_key: str | None) -> dict:
        account_key, requester_client_key = canonical_uuid(account_key), canonical_uuid(requester_client_key)
        self._require_identity(requester_client_key)

        account = self.account_repository.get_by_key(account_key)
        if account is None or account.client.client_key != requester_client_key:
            raise AccountNotFound(account_key)

        return AccountDTO.obj_to_dict(account)

    def update_limits(self, account_key: str, limits: dict) -> dict:
        account_key = canonical_uuid(account_key)
        account = next(iter(self.account_repository.get_many_for_update([account_key])), None)
        if account is None:
            raise AccountNotFound(account_key)

        single = limits["single_transfer_limit"]
        daily = limits["daily_transfer_limit"]
        if daily < single:
            raise InvalidAccountLimits()

        self.account_repository.update_limits(account, single, daily)
        response = AccountDTO.limits(account)
        self.session.commit()
        return response

    def update_status(self, account_key: str, new_status: str) -> dict:
        account_key = canonical_uuid(account_key)
        account = next(iter(self.account_repository.get_many_for_update([account_key])), None)
        if account is None:
            raise AccountNotFound(account_key)

        old_status = account.status.enumerator
        if old_status == AccountStatus.CLOSED and new_status != AccountStatus.CLOSED:
            raise AccountFinalStatus(old_status, new_status)

        if new_status == AccountStatus.CLOSED:
            total = account.balance + self.piggy_repository.reserved_balance(account.id)
            if total != 0:
                raise AccountMustHaveZeroBalanceToClose(account_key, total)
            self.piggy_repository.close_empty_for_account(account.id)

        if old_status != new_status:
            self.account_repository.update_status(account, new_status)

        response = AccountDTO.status(account)
        self.session.commit()
        return response

    def _require_identity(self, requester_client_key: str | None) -> None:
        if requester_client_key is None or requester_client_key == "":
            raise MissingClientIdentity()
