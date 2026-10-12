from errors.base_error import QIException


class BankNotFound(QIException):
    code = "QIT002001"
    def __init__(self, entity="Resource"):
        super().__init__("Not Found", self.code, 404, f"{entity} was not found.", "Recurso não encontrado.")


class DuplicateBankEntity(QIException):
    code = "QIT002002"
    def __init__(self):
        super().__init__("Duplicate Entity", self.code, 409, "A unique field is already registered.", "CPF, e-mail, conta ou nome do porquinho já cadastrado.")


class InvalidCustomer(QIException):
    code = "QIT002003"
    def __init__(self, reason):
        super().__init__("Invalid Customer", self.code, 422, reason, "Cliente deve ter CPF válido, data válida e idade mínima de 18 anos.")


class InsufficientBalance(QIException):
    code = "QIT002004"
    def __init__(self):
        super().__init__("Insufficient Balance", self.code, 422, "The balance does not cover the amount and fee.", "Saldo insuficiente para o valor e a tarifa.")


class InvalidBankState(QIException):
    code = "QIT002005"
    def __init__(self, reason):
        super().__init__("Invalid State", self.code, 409, reason, "O estado atual não permite esta operação.")


class IdempotencyConflict(QIException):
    code = "QIT002006"
    def __init__(self):
        super().__init__("Idempotency Conflict", self.code, 409, "This key was used with a different payload.", "Chave de idempotência já utilizada com outro corpo.")


class BalanceLimit(QIException):
    code = "QIT002007"
    def __init__(self):
        super().__init__("Balance Limit", self.code, 422, "The resulting balance exceeds the supported limit.", "O saldo resultante ultrapassa o limite suportado.")
