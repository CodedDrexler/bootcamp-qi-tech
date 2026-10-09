from controllers.base_controller import BaseController
from dtos import AccountDTO
from errors import AccountNotFound, ClientNotFound, MissingClientIdentity
from repositories import AccountRepository, ClientRepository


class AccountController(BaseController):
    """Criação e consulta de contas vinculadas a um cliente."""

    def __init__(self) -> None:
        super().__init__(__name__)
        self.client_repository = ClientRepository(self.context)
        self.account_repository = AccountRepository(self.context)

    def create(self, client_key: str, requester_client_key: str | None) -> dict:
        self._require_identity(requester_client_key)

        if requester_client_key != client_key:
            raise ClientNotFound(client_key)

        client = self.client_repository.get_by_key(client_key)
        if client is None:
            raise ClientNotFound(client_key)

        account = self.account_repository.create(client)
        account_dto = AccountDTO.only_key(account)
        self.session.commit()
        return account_dto

    def get_by_key(self, account_key: str, requester_client_key: str | None) -> dict:
        self._require_identity(requester_client_key)

        account = self.account_repository.get_by_key(account_key)
        if account is None or account.client.client_key != requester_client_key:
            # Mesmo erro para conta inexistente e conta alheia: evita IDOR.
            raise AccountNotFound(account_key)

        return AccountDTO.obj_to_dict(account)

    def _require_identity(self, requester_client_key: str | None) -> None:
        if requester_client_key is None or requester_client_key == "":
            raise MissingClientIdentity()
