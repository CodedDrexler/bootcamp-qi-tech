from uuid import uuid4
from sqlalchemy import (
    BigInteger,
    CHAR,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base


class PiggyBank(Base):
    __tablename__ = "piggy_bank"
    id = Column(Integer, primary_key=True)
    piggy_bank_key = Column(
        CHAR(36), nullable=False, unique=True, default=lambda: str(uuid4())
    )
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False, index=True)
    creation_request_key = Column(CHAR(36), nullable=False, unique=True)
    creation_fingerprint = Column(String(64), nullable=False)
    creation_response = Column(JSONB)
    name = Column(String(80), nullable=False)
    name_normalized = Column(String(160), nullable=False)
    description = Column(String(255))
    target_amount = Column(BigInteger, nullable=False)
    target_date = Column(Date)
    balance = Column(BigInteger, nullable=False, default=0)
    status = Column(String(10), nullable=False, default="active")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.clock_timestamp(),
        onupdate=func.clock_timestamp(),
    )
    __table_args__ = (
        UniqueConstraint(
            "account_id", "name_normalized", name="piggy_bank_unique_name"
        ),
        CheckConstraint("balance >= 0"),
        CheckConstraint("target_amount BETWEEN 1 AND 100000000"),
        CheckConstraint("status IN ('active','closed')"),
        CheckConstraint("version > 0"),
        CheckConstraint("status != 'closed' OR balance = 0"),
    )


class PiggyBankEvent(Base):
    __tablename__ = "piggy_bank_event"
    id = Column(BigInteger, primary_key=True)
    event_key = Column(
        CHAR(36), nullable=False, unique=True, default=lambda: str(uuid4())
    )
    piggy_bank_id = Column(
        Integer, ForeignKey("piggy_bank.id"), nullable=False, index=True
    )
    type = Column(String(10), nullable=False)
    version = Column(Integer, nullable=False)
    changes = Column(JSONB, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )
    __table_args__ = (
        CheckConstraint("type IN ('created','updated','closed')"),
        CheckConstraint("version > 0"),
    )
