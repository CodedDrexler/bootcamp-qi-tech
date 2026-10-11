from uuid import uuid4

from tests.utils.random_generator import RandomGenerator


class PayloadGenerator:
    @staticmethod
    def create_sample_entity_payload(
        hello: str = None,
        name: str = None,
        email: str = None,
        document_number: str = None,
        birthdate: str = None,
    ) -> dict:
        """Um cadastro valido, com qualquer campo trocado a pedido.

        Sem argumento nenhum o payload sai aleatorio no que precisa ser
        unico (e-mail e CPF), pra que dois cadastros seguidos nao batam
        na regra de duplicidade. Quem testa FILTRO precisa do contrario
        disso: um valor conhecido, pra poder procurar por ele depois.
        """
        if hello is None:
            hello = "world"

        if name is None:
            name = "Maria da Silva"

        if email is None:
            email = f"maria.silva.{uuid4()}@exemplo.com.br"

        if document_number is None:
            document_number = RandomGenerator.generate_cpf()

        if birthdate is None:
            birthdate = "1990-05-17"

        payload = {
            "hello": hello,
            "name": name,
            "email": email,
            "document_number": document_number,
            "birthdate": birthdate,
        }
        return payload

    @staticmethod
    def create_new_status_payload(new_status: str = None) -> dict:
        payload = {"status": new_status}
        return payload

    @staticmethod
    def create_client_payload(
        name: str = None,
        document_number: str = None,
        birth_date: str = None,
    ) -> dict:
        if name is None:
            name = "Ana Souza"
        if document_number is None:
            document_number = RandomGenerator.generate_cpf()
        if birth_date is None:
            birth_date = "1994-03-12"
        return {
            "name": name,
            "document_number": document_number,
            "birth_date": birth_date,
        }

    @staticmethod
    def create_deposit_payload(
        amount: int = 50000,
        request_control_key: str = None,
        funding_reference: str = None,
    ) -> dict:
        if request_control_key is None:
            request_control_key = str(uuid4())
        if funding_reference is None:
            funding_reference = str(uuid4())
        return {
            "request_control_key": request_control_key,
            "type": "deposit",
            "amount": amount,
            "funding_reference": funding_reference,
        }

    @staticmethod
    def create_transfer_payload(
        destination_account_key: str,
        amount: int = 20000,
        request_control_key: str = None,
    ) -> dict:
        if request_control_key is None:
            request_control_key = str(uuid4())
        return {
            "request_control_key": request_control_key,
            "type": "transfer",
            "amount": amount,
            "destination_account_key": destination_account_key,
        }

