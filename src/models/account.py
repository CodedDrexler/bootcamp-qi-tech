from sqlalchemy import BigInteger, CHAR, CheckConstraint, Column, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import relationship

from models.base import Base


class Account(Base):
    __tablename__ = "account"

    id = Column(Integer, primary_key=True)
    account_key = Column(CHAR(36), nullable=False)
    client_id = Column(Integer, ForeignKey("client.id"), nullable=False)
    balance = Column(BigInteger, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("account_key"),
        CheckConstraint("balance >= 0", name="account_balance_non_negative"),
    )

    client = relationship("Client", back_populates="accounts", lazy="selectin")
