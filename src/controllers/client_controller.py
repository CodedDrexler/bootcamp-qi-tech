from datetime import date

from controllers.base_controller import BaseController
from dtos import ClientDTO
from errors import (
    ClientNotFound,
    DuplicatedClientDocumentNumber,
    InvalidClientBirthDate,
    InvalidClientDocumentNumber,
    MissingClientIdentity,
    UnderageClient,
)
from repositories import ClientRepository
from utils.document_number import is_valid_cpf


MINIMUM_CLIENT_AGE = 18


class ClientController(BaseController):
    """Regras de cadastro e leitura de cliente."""

    def __init__(self) -> None:
        super().__init__(__name__)
        self.client_repository = ClientRepository(self.context)

    def create(self, client_data: dict) -> dict:
        document_number = client_data["document_number"]
        birth_date = self._parse_birth_date(client_data["birth_date"])

        if not is_valid_cpf(document_number):
            raise InvalidClientDocumentNumber(document_number)

        if self.client_repository.get_by_document_number(document_number) is not None:
            raise DuplicatedClientDocumentNumber(document_number)

        age = self._age_in_years(birth_date)
        if age < MINIMUM_CLIENT_AGE:
            raise UnderageClient(age, MINIMUM_CLIENT_AGE)

        client = self.client_repository.create(client_data)
        client_dto = ClientDTO.only_key(client)
        self.session.commit()
        return client_dto

    def get_by_key(self, client_key: str, requester_client_key: str | None) -> dict:
        self._require_identity(requester_client_key)

        # Para não confirmar a existência de outro cliente, identidade
        # diferente recebe o mesmo 404 de uma key inexistente (R8/IDOR).
        if requester_client_key != client_key:
            raise ClientNotFound(client_key)

        client = self.client_repository.get_by_key(client_key)
        if client is None:
            raise ClientNotFound(client_key)

        return ClientDTO.obj_to_dict(client)

    def _require_identity(self, requester_client_key: str | None) -> None:
        if requester_client_key is None or requester_client_key == "":
            raise MissingClientIdentity()

    def _parse_birth_date(self, raw_birth_date: str) -> date:
        try:
            return date.fromisoformat(raw_birth_date)
        except ValueError:
            raise InvalidClientBirthDate(raw_birth_date)

    def _age_in_years(self, birth_date: date) -> int:
        today = date.today()
        age = today.year - birth_date.year
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        return age
