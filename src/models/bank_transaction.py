from sqlalchemy import BigInteger, CHAR, CheckConstraint, Column, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import relationship

from models.base import Base


class BankTransaction(Base):
    __tablename__ = "bank_transaction"

    id = Column(BigInteger, primary_key=True)
    transaction_key = Column(CHAR(36), nullable=False)
    operation_key = Column(CHAR(36), nullable=False)
    request_control_key = Column(CHAR(36), nullable=True)
    type_id = Column(Integer, ForeignKey("transaction_type.id"), nullable=False)
    origin_account_id = Column(Integer, ForeignKey("account.id"), nullable=True)
    destination_account_id = Column(Integer, ForeignKey("account.id"), nullable=True)
    amount = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("transaction_key"),
        UniqueConstraint("request_control_key"),
        CheckConstraint("amount > 0", name="bank_transaction_amount_positive"),
        CheckConstraint(
            "origin_account_id IS NOT NULL OR destination_account_id IS NOT NULL",
            name="bank_transaction_has_account",
        ),
        CheckConstraint(
            "origin_account_id IS NULL OR destination_account_id IS NULL OR origin_account_id <> destination_account_id",
            name="bank_transaction_distinct_accounts",
        ),
    )

    type = relationship("TransactionType", foreign_keys=[type_id], lazy="selectin")
    origin_account = relationship("Account", foreign_keys=[origin_account_id], lazy="selectin")
    destination_account = relationship("Account", foreign_keys=[destination_account_id], lazy="selectin")
