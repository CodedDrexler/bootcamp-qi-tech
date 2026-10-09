from models import BankTransaction, TransactionType


class TransactionDTO:
    @staticmethod
    def operation_to_dict(transaction: BankTransaction, fee_amount: int = 0) -> dict:
        return {
            "transaction_key": transaction.transaction_key,
            "operation_key": transaction.operation_key,
            "request_control_key": transaction.request_control_key,
            "type": transaction.type.enumerator,
            "origin_account_key": (
                transaction.origin_account.account_key if transaction.origin_account is not None else None
            ),
            "destination_account_key": (
                transaction.destination_account.account_key if transaction.destination_account is not None else None
            ),
            "amount": transaction.amount,
            "fee_amount": fee_amount,
            "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
        }

    @staticmethod
    def statement_item(transaction: BankTransaction, account_id: int) -> dict:
        transaction_type = transaction.type.enumerator
        counterparty_account_key = None

        if transaction_type == TransactionType.DEPOSIT:
            direction = "credit"
            balance_effect = transaction.amount

        elif transaction_type == TransactionType.TRANSFER:
            if transaction.origin_account_id == account_id:
                direction = "debit"
                balance_effect = -transaction.amount
                if transaction.destination_account is not None:
                    counterparty_account_key = transaction.destination_account.account_key
            else:
                direction = "credit"
                balance_effect = transaction.amount
                if transaction.origin_account is not None:
                    counterparty_account_key = transaction.origin_account.account_key

        else:  # fee
            direction = "debit"
            balance_effect = -transaction.amount

        return {
            "transaction_key": transaction.transaction_key,
            "operation_key": transaction.operation_key,
            "type": transaction_type,
            "direction": direction,
            "amount": transaction.amount,
            "balance_effect": balance_effect,
            "counterparty_account_key": counterparty_account_key,
            "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
        }

    @staticmethod
    def statement_list(transactions: list[BankTransaction], account_id: int) -> list[dict]:
        return [TransactionDTO.statement_item(transaction, account_id) for transaction in transactions]
