from sqlalchemy import BigInteger, CHAR, CheckConstraint, Column, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import relationship

from models.base import Base


class Account(Base):
    __tablename__ = "account"

    id = Column(Integer, primary_key=True)
    account_key = Column(CHAR(36), nullable=False)
    client_id = Column(Integer, ForeignKey("client.id"), nullable=False)
    status_id = Column(Integer, ForeignKey("account_status.id"), nullable=False)
    balance = Column(BigInteger, nullable=False, default=0, server_default="0")
    single_transfer_limit = Column(BigInteger, nullable=False)
    daily_transfer_limit = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("account_key"),
        UniqueConstraint("client_id"),
        CheckConstraint("balance >= 0", name="account_balance_non_negative"),
        CheckConstraint("single_transfer_limit > 0", name="account_single_transfer_limit_positive"),
        CheckConstraint("daily_transfer_limit > 0", name="account_daily_transfer_limit_positive"),
        CheckConstraint(
            "daily_transfer_limit >= single_transfer_limit",
            name="account_daily_limit_not_below_single_limit",
        ),
    )

    client = relationship("Client", back_populates="account", lazy="selectin")
    status = relationship("AccountStatus", foreign_keys=[status_id], lazy="selectin")
