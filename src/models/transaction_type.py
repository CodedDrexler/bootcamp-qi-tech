from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint, func

from models.base import Base


class TransactionType(Base):
    __tablename__ = "transaction_type"

    id = Column(Integer, primary_key=True)
    enumerator = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("enumerator"),)

    DEPOSIT = "deposit"
    TRANSFER = "transfer"
    FEE = "fee"
    RESERVE = "reserve"
    REDEEM = "redeem"
