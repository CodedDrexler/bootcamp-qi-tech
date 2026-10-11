from sqlalchemy import Column, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import relationship

from models.base import Base


class AccountStatusEvent(Base):
    __tablename__ = "account_status_event"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    status_id = Column(Integer, ForeignKey("account_status.id"), nullable=False)
    event_datetime = Column(DateTime, nullable=False, server_default=func.now())
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    account = relationship("Account", foreign_keys=[account_id])
    status = relationship("AccountStatus", foreign_keys=[status_id], lazy="selectin")
