from datetime import date

from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from constants import MINIMUM_CLIENT_AGE
from dtos import ClientDTO
from errors import (
    ClientNotFound,
    DuplicatedClientDocumentNumber,
    FutureClientBirthDate,
    InvalidClientBirthDate,
    InvalidClientDocumentNumber,
    MissingClientIdentity,
    UnderageClient,
)
from repositories import ClientRepository
from utils.document_number import is_valid_cpf
from utils.identifiers import canonical_uuid


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

        if birth_date > date.today():
            raise FutureClientBirthDate(client_data["birth_date"])

        if self.client_repository.get_by_document_number(document_number) is not None:
            raise DuplicatedClientDocumentNumber(document_number)

        age = self._age_in_years(birth_date)
        if age < MINIMUM_CLIENT_AGE:
            raise UnderageClient(age, MINIMUM_CLIENT_AGE)

        client = self.client_repository.create(client_data)

        # A checagem acima melhora a mensagem no caso comum; o UNIQUE do
        # banco fecha a corrida de duas requisições simultâneas com o mesmo CPF.
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            if self.client_repository.get_by_document_number(document_number) is not None:
                raise DuplicatedClientDocumentNumber(document_number)
            raise

        client_dto = ClientDTO.only_key(client)
        self.session.commit()
        return client_dto

    def get_by_key(self, client_key: str, requester_client_key: str | None) -> dict:
        client_key, requester_client_key = canonical_uuid(client_key), canonical_uuid(requester_client_key)
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
