from datetime import date
import hashlib
import json
from sqlalchemy.exc import IntegrityError
from controllers.base_controller import BaseController
from dtos.bank_dto import account_dto, customer_dto, entry_dto, event_dto, page_dto, piggy_dto, transaction_dto
from errors.bank_errors import BalanceLimit, BankNotFound, DuplicateBankEntity, IdempotencyConflict, InsufficientBalance, InvalidBankState, InvalidCustomer
from errors.base_error import InvalidSchema
from models.bank import MAX_MONEY, Account, BankTransaction, Customer, LedgerEntry, PiggyBank, StatusEvent
from repositories.bank_repository import BankRepository
from utils.document_number import is_valid_cpf

TRANSFER_FEE = 100


class BankController(BaseController):
    def __init__(self):
        super().__init__(__name__)
        self.repo = BankRepository(self.session)

    def execute(self, scope, key, payload, operation):
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        try:
            record, new = self.repo.claim(scope, key, fingerprint)
            if record.fingerprint != fingerprint:
                raise IdempotencyConflict()
            if not new:
                response = record.response
                self.session.commit()
                return response
            response = operation()
            record.response = response
            self.session.commit()
            self.logger.info("bank_operation_completed scope=%s", scope)
            return response
        except IntegrityError as error:
            self.session.rollback()
            if getattr(error.orig, "pgcode", None) == "23505":
                raise DuplicateBankEntity() from None
            raise

    def create_customer(self, payload):
        if not is_valid_cpf(payload["document_number"]):
            raise InvalidCustomer("Invalid CPF check digits.")
        try:
            birth = date.fromisoformat(payload["birthdate"])
        except ValueError:
            raise InvalidCustomer("Invalid birthdate.") from None
        today = date.today()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        if age < 18 or age > 120:
            raise InvalidCustomer("Age must be between 18 and 120 years.")
        data = {**payload, "birthdate": birth, "email": payload["email"].strip().lower(), "name": payload["name"].strip()}
        c = self.repo.add(Customer, **data)
        return {"customer_key": c.customer_key}

    def customer(self, key):
        c = self.repo.find(Customer, customer_key=key)
        if c is None:
            raise BankNotFound("Customer")
        return c

    def create_account(self, payload):
        c = self.customer(payload["customer_key"])
        a = self.repo.add(Account, customer_id=c.id, balance=0, status="ACTIVE")
        self.repo.add(StatusEvent, account_id=a.id, status="ACTIVE")
        return {"account_key": a.account_key}

    def account(self, key, lock=False):
        a = (self.repo.lock_accounts([key]) or [None])[0] if lock else self.repo.find(Account, account_key=key)
        if a is None:
            raise BankNotFound("Account")
        return a

    @staticmethod
    def active(entity):
        if entity.status != "ACTIVE":
            raise InvalidBankState("The account or piggy bank is closed.")

    @staticmethod
    def change_balance(entity, delta):
        result = entity.balance + delta
        if result < 0:
            raise InsufficientBalance()
        if result > MAX_MONEY:
            raise BalanceLimit()
        entity.balance = result

    def get_account(self, key):
        # The parent lock gives a consistent snapshot across checking and reserves.
        a = self.account(key, lock=True)
        response = account_dto(a, self.repo.customer_for_account(a).customer_key, self.repo.piggies(a.id))
        response["status_events"] = [event_dto(e) for e in self.repo.events(a.id)]
        return response

    def close_account(self, key):
        a = self.account(key, lock=True)
        if a.status == "CLOSED":
            return self.get_account(key)
        if a.balance or any(p.balance for p in self.repo.piggies(a.id)):
            raise InvalidBankState("Checking and reserves must be empty before closing.")
        a.status = "CLOSED"
        self.repo.add(StatusEvent, account_id=a.id, status="CLOSED")
        response = self.get_account(key)
        self.session.commit()
        return response

    def entry(self, t, amount, kind, account=None, piggy=None, pocket="CHECKING"):
        after = piggy.balance if piggy else (account.balance if account else None)
        self.repo.add(LedgerEntry, transaction_id=t.id, account_id=account.id if account else None,
                      piggy_bank_id=piggy.id if piggy else None, pocket=pocket, type=kind,
                      amount=amount, balance_after=after)

    def transact(self, key, payload):
        kind, amount = payload["type"], payload["amount"]
        dest_key = payload.get("destination_account_key")
        if (kind == "TRANSFER") != (dest_key is not None):
            raise InvalidSchema("destination_account_key is required only for TRANSFER.")
        if dest_key == key:
            raise InvalidBankState("An account cannot transfer to itself.")
        keys = [key, dest_key] if dest_key else [key]
        accounts = {a.account_key: a for a in self.repo.lock_accounts(keys)}
        if any(k not in accounts for k in keys):
            raise BankNotFound("Account")
        for a in accounts.values():
            self.active(a)
        origin = accounts[key]
        fee = TRANSFER_FEE if kind == "TRANSFER" else 0
        t = self.repo.add(BankTransaction, type=kind, amount=amount, fee=fee)
        if kind == "DEPOSIT":
            self.change_balance(origin, amount)
            self.entry(t, amount, kind, origin)
            self.entry(t, -amount, kind, pocket="CLEARING")
        else:
            self.change_balance(origin, -amount)
            self.entry(t, -amount, kind, origin)
            if kind == "WITHDRAWAL":
                self.entry(t, amount, kind, pocket="CLEARING")
            else:
                self.change_balance(origin, -fee)
                self.entry(t, -fee, "FEE", origin)
                dest = accounts[dest_key]
                self.change_balance(dest, amount)
                self.entry(t, amount, kind, dest)
                self.entry(t, fee, "FEE", pocket="FEES")
        return transaction_dto(t)

    def create_piggy(self, key, payload):
        a = self.account(key, lock=True)
        self.active(a)
        p = self.repo.add(PiggyBank, account_id=a.id, name=payload["name"].strip(),
                          target_amount=payload["target_amount"], balance=0, status="ACTIVE")
        self.repo.add(StatusEvent, account_id=a.id, piggy_bank_id=p.id, status="ACTIVE")
        return {"piggy_bank_key": p.piggy_bank_key}

    def piggy(self, a, key, lock=False):
        p = self.repo.lock_piggy(a.id, key) if lock else self.repo.find(PiggyBank, account_id=a.id, piggy_bank_key=key)
        if p is None:
            raise BankNotFound("Piggy bank")
        return p

    def get_piggy(self, key, piggy_key):
        a = self.account(key)
        p = self.piggy(a, piggy_key)
        response = piggy_dto(p, key)
        response["status_events"] = [event_dto(e) for e in self.repo.events(a.id, p.id)]
        return response

    def close_piggy(self, key, piggy_key):
        a = self.account(key, lock=True)
        p = self.piggy(a, piggy_key, lock=True)
        if p.status == "CLOSED":
            return self.get_piggy(key, piggy_key)
        if p.balance:
            raise InvalidBankState("Redeem the full reserve before closing.")
        p.status = "CLOSED"
        self.repo.add(StatusEvent, account_id=a.id, piggy_bank_id=p.id, status="CLOSED")
        response = self.get_piggy(key, piggy_key)
        self.session.commit()
        return response

    def transact_piggy(self, key, piggy_key, payload):
        a = self.account(key, lock=True)
        self.active(a)
        p = self.piggy(a, piggy_key, lock=True)
        self.active(p)
        kind, amount = payload["type"], payload["amount"]
        delta = amount if kind == "SAVE" else -amount
        self.change_balance(a, -delta)
        self.change_balance(p, delta)
        t = self.repo.add(BankTransaction, type=kind, amount=amount, fee=0)
        self.entry(t, -delta, kind, a)
        self.entry(t, delta, kind, a, p, "PIGGY")
        return transaction_dto(t)

    def statement(self, key, piggy_key, limit, page):
        a = self.account(key)
        pid = self.piggy(a, piggy_key).id if piggy_key else None
        return page_dto(self.repo.statement(a.id, pid, limit, page), limit, page, entry_dto)

    def list_customers(self, limit, page):
        return page_dto(self.repo.page(Customer, limit, page), limit, page, customer_dto)

    def list_accounts(self, limit, page):
        def convert(a):
            return {"account_key": a.account_key, "customer_key": self.repo.customer_for_account(a).customer_key,
                    "balance": a.balance, "status": a.status, "currency": "BRL"}
        return page_dto(self.repo.page(Account, limit, page), limit, page, convert)

    def list_piggies(self, key, limit, page):
        a = self.account(key)
        return page_dto(self.repo.page(PiggyBank, limit, page, account_id=a.id), limit, page, lambda p: piggy_dto(p, key))
