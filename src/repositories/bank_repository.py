from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from models.bank import Account, BankTransaction, Customer, IdempotencyRecord, LedgerEntry, PiggyBank, StatusEvent


class BankRepository:
    def __init__(self, session):
        self.session = session

    def add(self, model, **fields):
        obj = model(**fields)
        self.session.add(obj)
        self.session.flush()
        return obj

    def find(self, model, **fields):
        return self.session.scalar(select(model).filter_by(**fields))

    def page(self, model, limit, page, **fields):
        return self.session.scalars(select(model).filter_by(**fields).order_by(model.id.desc())
                                    .limit(limit + 1).offset(limit * page)).all()

    def lock_accounts(self, keys):
        return self.session.scalars(select(Account).where(Account.account_key.in_(keys))
                                    .order_by(Account.id).with_for_update()
                                    .execution_options(populate_existing=True)).all()

    def lock_piggy(self, account_id, key):
        return self.session.scalar(select(PiggyBank).filter_by(account_id=account_id, piggy_bank_key=key)
                                   .with_for_update().execution_options(populate_existing=True))

    def piggies(self, account_id):
        return self.session.scalars(select(PiggyBank).filter_by(account_id=account_id).order_by(PiggyBank.id)).all()

    def claim(self, scope, key, fingerprint):
        new_id = self.session.scalar(insert(IdempotencyRecord).values(scope=scope, key=key, fingerprint=fingerprint)
                                     .on_conflict_do_nothing(constraint="uq_idempotency_scope_key")
                                     .returning(IdempotencyRecord.id))
        record = self.session.scalar(select(IdempotencyRecord).filter_by(scope=scope, key=key).with_for_update())
        return record, new_id is not None

    def customer_for_account(self, account):
        return self.session.get(Customer, account.customer_id)

    def events(self, account_id, piggy_bank_id=None):
        return self.session.scalars(select(StatusEvent).filter_by(account_id=account_id, piggy_bank_id=piggy_bank_id)
                                    .order_by(StatusEvent.id)).all()

    def statement(self, account_id, piggy_bank_id, limit, page):
        stmt = (select(LedgerEntry, BankTransaction.transaction_key)
                .join(BankTransaction, LedgerEntry.transaction_id == BankTransaction.id)
                .where(LedgerEntry.account_id == account_id, LedgerEntry.piggy_bank_id == piggy_bank_id)
                .order_by(LedgerEntry.id.desc()).limit(limit + 1).offset(limit * page))
        return self.session.execute(stmt).all()
