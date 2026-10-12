from sqlalchemy import func
from models.piggy_bank import PiggyBank, PiggyBankEvent
from models import BankTransaction
from utils.identifiers import canonical_uuid


class PiggyBankRepository:
    def __init__(self, context):
        self.session = context.db_session

    def get_by_key(self, account_id, key, for_update=False):
        query = self.session.query(PiggyBank).filter_by(
            account_id=account_id, piggy_bank_key=canonical_uuid(key)
        )
        if for_update:
            query = query.with_for_update().populate_existing()
        return query.first()

    def get_by_creation_key(self, key):
        return (
            self.session.query(PiggyBank)
            .filter_by(creation_request_key=canonical_uuid(key))
            .first()
        )

    def get_by_name(self, account_id, name):
        return (
            self.session.query(PiggyBank)
            .filter_by(account_id=account_id, name_normalized=name)
            .first()
        )

    def create(self, **data):
        piggy = PiggyBank(**data)
        self.session.add(piggy)
        self.session.flush()
        return piggy

    def event(self, piggy, kind, changes):
        event = PiggyBankEvent(
            piggy_bank_id=piggy.id, type=kind, version=piggy.version, changes=changes
        )
        self.session.add(event)
        return event

    def list_page(self, account_id, limit, page, status=None):
        query = self.session.query(PiggyBank).filter_by(account_id=account_id)
        if status:
            query = query.filter_by(status=status)
        return (
            query.order_by(PiggyBank.id.desc())
            .limit(limit + 1)
            .offset(limit * page)
            .all()
        )

    def list_events(self, piggy_id, limit, page):
        return (
            self.session.query(PiggyBankEvent)
            .filter_by(piggy_bank_id=piggy_id)
            .order_by(PiggyBankEvent.id.desc())
            .limit(limit + 1)
            .offset(limit * page)
            .all()
        )

    def list_transactions(self, piggy_id, limit, page):
        return (
            self.session.query(BankTransaction)
            .filter_by(piggy_bank_id=piggy_id)
            .order_by(BankTransaction.id.desc())
            .limit(limit + 1)
            .offset(limit * page)
            .all()
        )

    def reserved_balance(self, account_id):
        return int(
            self.session.query(func.coalesce(func.sum(PiggyBank.balance), 0))
            .filter_by(account_id=account_id)
            .scalar()
        )

    def close_empty_for_account(self, account_id):
        piggies = (
            self.session.query(PiggyBank)
            .filter_by(account_id=account_id, status="active")
            .order_by(PiggyBank.id)
            .with_for_update()
            .all()
        )
        for piggy in piggies:
            piggy.status = "closed"
            piggy.version += 1
            self.event(
                piggy,
                "closed",
                {
                    "status": {"from": "active", "to": "closed"},
                    "reason": "account_closure",
                },
            )
