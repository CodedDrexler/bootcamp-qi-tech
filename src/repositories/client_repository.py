from datetime import date
from uuid import uuid4

from database import Context
from models import Client


class ClientRepository:
    """Persistência de clientes. Regras de negócio ficam no controller."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, client_data: dict) -> Client:
        client = Client()
        client.client_key = str(uuid4())
        client.name = client_data["name"]
        client.document_number = client_data["document_number"]
        client.birth_date = date.fromisoformat(client_data["birth_date"])
        self.session.add(client)
        return client

    def get_by_key(self, client_key: str) -> Client:
        return self.session.query(Client).filter(Client.client_key == client_key).first()

    def get_by_document_number(self, document_number: str) -> Client:
        return self.session.query(Client).filter(Client.document_number == document_number).first()
