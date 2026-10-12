from errors.base_error import QIException


class PiggyBankNotFound(QIException):
    code = "QIT006001"
    def __init__(self):
        super().__init__("Piggy bank not found", self.code, 404, "The piggy bank does not belong to this account or does not exist.", "O porquinho não foi encontrado nesta conta.")


class PiggyBankDuplicateName(QIException):
    code = "QIT006002"
    def __init__(self):
        super().__init__("Piggy bank name already used", self.code, 409, "This normalized name is already used in the account.", "Este nome já está em uso em um porquinho desta conta.")


class PiggyBankNotOperational(QIException):
    code = "QIT006003"
    def __init__(self):
        super().__init__("Piggy bank is closed", self.code, 423, "Closed piggy banks cannot be modified or moved.", "O porquinho está encerrado e não pode ser alterado ou movimentado.")


class InsufficientReservedBalance(QIException):
    code = "QIT006004"
    def __init__(self):
        super().__init__("Insufficient reserved balance", self.code, 422, "The reserve does not cover the redemption amount.", "O saldo reservado não cobre o valor do resgate.")


class PiggyBankMustBeEmpty(QIException):
    code = "QIT006005"
    def __init__(self):
        super().__init__("Piggy bank is not empty", self.code, 409, "Redeem the reserve before closing the piggy bank.", "Resgate todo o saldo antes de encerrar o porquinho.")


class PiggyBankVersionConflict(QIException):
    code = "QIT006006"
    def __init__(self):
        super().__init__("Piggy bank version conflict", self.code, 409, "Read the current metadata version before updating.", "O porquinho foi alterado. Consulte a versão atual antes de salvar.")


class InvalidPiggyBankDate(QIException):
    code = "QIT006007"
    def __init__(self):
        super().__init__("Invalid target date", self.code, 422, "The target date must be a real date and cannot be in the past when set.", "A data da meta deve existir e não pode estar no passado ao ser definida.")


class BankingUnavailable(QIException):
    code = "QIT006008"
    def __init__(self):
        super().__init__("Bank temporarily unavailable", self.code, 503, "The database is unavailable or the operation exceeded its deadline. Retry using the original request key.", "Banco indisponível ou prazo excedido. Tente novamente com a mesma chave do pedido.")
