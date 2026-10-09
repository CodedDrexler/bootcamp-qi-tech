from models import Client


class ClientDTO:
    @staticmethod
    def only_key(client: Client) -> dict:
        return {"client_key": client.client_key}

    @staticmethod
    def obj_to_dict(client: Client) -> dict:
        return {
            "client_key": client.client_key,
            "name": client.name,
            "document_number": client.document_number,
            "birth_date": client.birth_date.isoformat(),
            "created_at": client.created_at.isoformat() if client.created_at else None,
        }
