from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, Integer, String, UniqueConstraint, func

from models.base import Base


class BillingConfiguration(Base):
    __tablename__ = "billing_configuration"

    id = Column(Integer, primary_key=True)
    operation_type = Column(String(50), nullable=False)
    expense_type = Column(String(30), nullable=False)
    fixed_amount_cents = Column(BigInteger, nullable=True)
    percentage_basis_points = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("operation_type"),
        CheckConstraint(
            "expense_type IN ('fixed_amount', 'percentage')",
            name="billing_configuration_expense_type",
        ),
        CheckConstraint(
            "(expense_type = 'fixed_amount' AND fixed_amount_cents IS NOT NULL "
            "AND fixed_amount_cents > 0 AND percentage_basis_points IS NULL) "
            "OR (expense_type = 'percentage' AND fixed_amount_cents IS NULL "
            "AND percentage_basis_points IS NOT NULL AND percentage_basis_points > 0 "
            "AND percentage_basis_points <= 10000)",
            name="billing_configuration_shape",
        ),
    )

    FIXED_AMOUNT = "fixed_amount"
    PERCENTAGE = "percentage"
    TRANSFER = "transfer"
