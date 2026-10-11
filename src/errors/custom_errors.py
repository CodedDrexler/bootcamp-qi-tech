from errors import QIException


class NotFoundSampleEntity(QIException):
    code = "QIT001001"

    def __init__(self, sample_entity_key) -> None:
        title = "Entity not Found"
        http_status = 404
        description = f"Entity with key {sample_entity_key} was not found."
        translation = f"A entidade com chave {sample_entity_key} não foi encontrada."
        super().__init__(title, self.code, http_status, description, translation)


class SampleEntityFinalStatus(QIException):
    code = "QIT001002"

    def __init__(self, old_status, new_status) -> None:
        title = "Entity cannot change status"
        http_status = 409
        description = f"Entity with status {old_status} cannot update to {new_status}."
        translation = "Essa entidade não pode ser atualizada."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidDocumentNumber(QIException):
    """O CPF tem o formato certo e não existe.

    422, e não 400, de propósito: 400 quer dizer "não consegui ler o seu
    pedido". Aqui a API leu, entendeu, e o valor é que não pode existir —
    os dois últimos dígitos não batem com a conta. A diferença está
    explicada em src/utils/document_number.py.
    """

    code = "QIT001003"

    def __init__(self, document_number) -> None:
        title = "Invalid Document Number"
        http_status = 422
        description = f"The document number {document_number} is not a valid CPF."
        translation = "O CPF informado não é válido."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedDocumentNumber(QIException):
    """Já existe um cadastro com este CPF.

    409 Conflict: o pedido está correto em si, e o que impede é o que já
    está no banco. É a mesma família do SampleEntityFinalStatus aqui em
    cima — conflito com o que já existe, não erro de quem pediu.
    """

    code = "QIT001004"

    def __init__(self, document_number) -> None:
        title = "Document Number already registered"
        http_status = 409
        description = f"There is already an entity with the document number {document_number}."
        translation = "Já existe um cadastro com este CPF."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedEmail(QIException):
    code = "QIT001005"

    def __init__(self, email) -> None:
        title = "Email already registered"
        http_status = 409
        description = f"There is already an entity with the email {email}."
        translation = "Já existe um cadastro com este e-mail."
        super().__init__(title, self.code, http_status, description, translation)


class UnderageSampleEntity(QIException):
    code = "QIT001006"

    def __init__(self, age, minimum_age) -> None:
        title = "Entity is underage"
        http_status = 422
        description = f"The entity is {age} years old, and the minimum is {minimum_age}."
        translation = f"É preciso ter pelo menos {minimum_age} anos."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidBirthdate(QIException):
    """A data tem o formato certo e não existe no calendário.

    Existe porque o `pattern` do schema sabe contar dígitos, não dias:
    "2025-02-30" e "9999-99-99" passam pelo regex e morrem no
    `date.fromisoformat`. Sem esta classe, esse ValueError virava 500 —
    a API culpando a si mesma por um erro de quem chamou.
    """

    code = "QIT001007"

    def __init__(self, birthdate) -> None:
        title = "Invalid Birthdate"
        http_status = 422
        description = f"The birthdate {birthdate} is not a real date."
        translation = "A data de nascimento informada não existe."
        super().__init__(title, self.code, http_status, description, translation)


# ============================================================================
# Domínio bancário
# ============================================================================


class ClientNotFound(QIException):
    code = "QIT002001"

    def __init__(self, client_key) -> None:
        title = "Client not found"
        http_status = 404
        description = f"Client with key {client_key} was not found."
        translation = "O cliente informado não foi encontrado."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidClientDocumentNumber(QIException):
    code = "QIT002002"

    def __init__(self, document_number) -> None:
        title = "Invalid client document number"
        http_status = 422
        description = f"The document number {document_number} is not a valid CPF."
        translation = "O CPF informado não é válido."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedClientDocumentNumber(QIException):
    code = "QIT002003"

    def __init__(self, document_number) -> None:
        title = "Client document already registered"
        http_status = 409
        description = f"There is already a client with the document number {document_number}."
        translation = "Já existe um cliente com este CPF."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidClientBirthDate(QIException):
    code = "QIT002004"

    def __init__(self, birth_date) -> None:
        title = "Invalid client birth date"
        http_status = 422
        description = f"The birth date {birth_date} is not a real date."
        translation = "A data de nascimento informada não existe."
        super().__init__(title, self.code, http_status, description, translation)


class UnderageClient(QIException):
    code = "QIT002005"

    def __init__(self, age, minimum_age) -> None:
        title = "Client is underage"
        http_status = 422
        description = f"The client is {age} years old, and the minimum is {minimum_age}."
        translation = f"É preciso ter pelo menos {minimum_age} anos para abrir conta neste MVP."
        super().__init__(title, self.code, http_status, description, translation)




class FutureClientBirthDate(QIException):
    code = "QIT002006"

    def __init__(self, birth_date) -> None:
        title = "Client birth date is in the future"
        http_status = 422
        description = f"The birth date {birth_date} is in the future."
        translation = "A data de nascimento não pode estar no futuro."
        super().__init__(title, self.code, http_status, description, translation)


class AccountNotFound(QIException):
    code = "QIT003001"

    def __init__(self, account_key) -> None:
        title = "Account not found"
        http_status = 404
        description = f"Account with key {account_key} was not found."
        translation = "A conta informada não foi encontrada."
        super().__init__(title, self.code, http_status, description, translation)




class AccountAlreadyExists(QIException):
    code = "QIT003002"

    def __init__(self, client_key) -> None:
        title = "Account already exists"
        http_status = 409
        description = f"Client {client_key} already has an account in this MVP."
        translation = "Este cliente já possui uma conta."
        super().__init__(title, self.code, http_status, description, translation)


class InsufficientBalance(QIException):
    code = "QIT004001"

    def __init__(self, available_balance, required_amount) -> None:
        title = "Insufficient balance"
        http_status = 422
        description = (
            f"Available balance is {available_balance} cents, but {required_amount} cents are required."
        )
        translation = "Saldo insuficiente para concluir a transferência e a tarifa."
        super().__init__(title, self.code, http_status, description, translation)


class SameAccountTransfer(QIException):
    code = "QIT004002"

    def __init__(self) -> None:
        title = "Invalid transfer accounts"
        http_status = 409
        description = "Origin and destination accounts must be different."
        translation = "A conta de origem e a conta de destino devem ser diferentes."
        super().__init__(title, self.code, http_status, description, translation)


class RequestControlKeyConflict(QIException):
    code = "QIT004003"

    def __init__(self, request_control_key) -> None:
        title = "Idempotency key conflict"
        http_status = 409
        description = (
            f"The request_control_key {request_control_key} was already used by a different operation."
        )
        translation = "A chave de idempotência já foi usada por uma operação diferente."
        super().__init__(title, self.code, http_status, description, translation)


class AccountNotOperational(QIException):
    code = "QIT003003"

    def __init__(self, account_key, account_status) -> None:
        title = "Account is not operational"
        http_status = 423
        description = f"Account {account_key} is {account_status} and cannot perform this operation."
        translation = "Contas bloqueadas ou encerradas não podem realizar esta operação."
        super().__init__(title, self.code, http_status, description, translation)


class AccountMustHaveZeroBalanceToClose(QIException):
    code = "QIT003004"

    def __init__(self, account_key, balance) -> None:
        title = "Account cannot be closed with balance"
        http_status = 409
        description = f"Account {account_key} has {balance} cents and must reach zero before closing."
        translation = "A conta precisa estar com saldo zero para ser encerrada."
        super().__init__(title, self.code, http_status, description, translation)


class AccountFinalStatus(QIException):
    code = "QIT003005"

    def __init__(self, old_status, new_status) -> None:
        title = "Account status cannot change"
        http_status = 409
        description = f"Account with status {old_status} cannot update to {new_status}."
        translation = "Uma conta encerrada não pode mudar de status."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidAccountLimits(QIException):
    code = "QIT003006"

    def __init__(self) -> None:
        title = "Invalid account limits"
        http_status = 422
        description = "Daily transfer limit must be greater than or equal to the single transfer limit."
        translation = "O limite diário deve ser maior ou igual ao limite por transferência."
        super().__init__(title, self.code, http_status, description, translation)


class TransferLimitExceeded(QIException):
    code = "QIT004004"

    def __init__(self, amount, limit) -> None:
        title = "Transfer limit exceeded"
        http_status = 422
        description = f"Transfer amount is {amount} cents and the account limit is {limit} cents."
        translation = "O valor da transferência excede o limite por operação da conta."
        super().__init__(title, self.code, http_status, description, translation)


class DailyTransferLimitExceeded(QIException):
    code = "QIT004005"

    def __init__(self, amount_today, requested_amount, daily_limit) -> None:
        title = "Daily transfer limit exceeded"
        http_status = 422
        description = (
            f"Account already transferred {amount_today} cents today; adding {requested_amount} "
            f"cents exceeds the daily limit of {daily_limit} cents."
        )
        translation = "A transferência excede o limite diário disponível da conta."
        super().__init__(title, self.code, http_status, description, translation)


class FundingReferenceConflict(QIException):
    code = "QIT004006"

    def __init__(self, funding_reference) -> None:
        title = "Funding reference conflict"
        http_status = 409
        description = f"The funding reference {funding_reference} was already applied."
        translation = "A referência externa deste aporte já foi utilizada."
        super().__init__(title, self.code, http_status, description, translation)


class MissingClientIdentity(QIException):
    code = "QIT005001"

    def __init__(self) -> None:
        title = "Client identity required"
        http_status = 401
        description = "The trusted X-CLIENT-KEY identity header is required for this resource."
        translation = "A identidade do cliente é obrigatória para acessar este recurso."
        super().__init__(title, self.code, http_status, description, translation)
