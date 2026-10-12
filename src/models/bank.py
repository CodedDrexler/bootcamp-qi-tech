from uuid import uuid4
from sqlalchemy import BigInteger, CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base

MAX_MONEY = 9_000_000_000_000_000


class Customer(Base):
    __tablename__ = "customer"
    id = Column(Integer, primary_key=True)
    customer_key = Column(String(36), nullable=False, unique=True, default=lambda: str(uuid4()))
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    document_number = Column(String(14), nullable=False, unique=True)
    birthdate = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Account(Base):
    __tablename__ = "account"
    id = Column(Integer, primary_key=True)
    account_key = Column(String(36), nullable=False, unique=True, default=lambda: str(uuid4()))
    customer_id = Column(Integer, ForeignKey("customer.id"), nullable=False, unique=True)
    balance = Column(BigInteger, nullable=False, default=0)
    status = Column(String(10), nullable=False, default="ACTIVE")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (CheckConstraint(f"balance BETWEEN 0 AND {MAX_MONEY}"),
                      CheckConstraint("status IN ('ACTIVE','CLOSED')"),
                      CheckConstraint("status != 'CLOSED' OR balance = 0"))


class PiggyBank(Base):
    __tablename__ = "piggy_bank"
    id = Column(Integer, primary_key=True)
    piggy_bank_key = Column(String(36), nullable=False, unique=True, default=lambda: str(uuid4()))
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    target_amount = Column(BigInteger, nullable=False)
    balance = Column(BigInteger, nullable=False, default=0)
    status = Column(String(10), nullable=False, default="ACTIVE")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint("account_id", "name"),
                      CheckConstraint(f"balance BETWEEN 0 AND {MAX_MONEY}"),
                      CheckConstraint(f"target_amount BETWEEN 1 AND {MAX_MONEY}"),
                      CheckConstraint("status IN ('ACTIVE','CLOSED')"),
                      CheckConstraint("status != 'CLOSED' OR balance = 0"))


class BankTransaction(Base):
    __tablename__ = "bank_transaction"
    id = Column(Integer, primary_key=True)
    transaction_key = Column(String(36), nullable=False, unique=True, default=lambda: str(uuid4()))
    type = Column(String(12), nullable=False)
    amount = Column(BigInteger, nullable=False)
    fee = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (CheckConstraint("type IN ('DEPOSIT','WITHDRAWAL','TRANSFER','SAVE','REDEEM')"),
                      CheckConstraint(f"amount BETWEEN 1 AND {MAX_MONEY}"), CheckConstraint("fee >= 0"))


class LedgerEntry(Base):
    __tablename__ = "ledger_entry"
    id = Column(Integer, primary_key=True)
    entry_key = Column(String(36), nullable=False, unique=True, default=lambda: str(uuid4()))
    transaction_id = Column(Integer, ForeignKey("bank_transaction.id"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("account.id"), index=True)
    piggy_bank_id = Column(Integer, ForeignKey("piggy_bank.id"), index=True)
    pocket = Column(String(10), nullable=False)
    type = Column(String(12), nullable=False)
    amount = Column(BigInteger, nullable=False)
    balance_after = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (CheckConstraint("amount != 0"),
                      CheckConstraint("pocket IN ('CHECKING','PIGGY','CLEARING','FEES')"),
                      CheckConstraint("(pocket = 'CHECKING' AND account_id IS NOT NULL AND piggy_bank_id IS NULL AND balance_after IS NOT NULL) OR (pocket = 'PIGGY' AND account_id IS NOT NULL AND piggy_bank_id IS NOT NULL AND balance_after IS NOT NULL) OR (pocket IN ('CLEARING','FEES') AND account_id IS NULL AND piggy_bank_id IS NULL AND balance_after IS NULL)"),
                      CheckConstraint(f"balance_after IS NULL OR balance_after BETWEEN 0 AND {MAX_MONEY}"))


class StatusEvent(Base):
    __tablename__ = "bank_status_event"
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False, index=True)
    piggy_bank_id = Column(Integer, ForeignKey("piggy_bank.id"))
    status = Column(String(10), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (CheckConstraint("status IN ('ACTIVE','CLOSED')"),)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_record"
    id = Column(Integer, primary_key=True)
    scope = Column(String(200), nullable=False)
    key = Column(String(128), nullable=False)
    fingerprint = Column(String(64), nullable=False)
    response = Column(JSONB)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),)
