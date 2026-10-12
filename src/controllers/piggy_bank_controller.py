from datetime import date
import hashlib
import json
from sqlalchemy.exc import IntegrityError
from controllers.base_controller import BaseController
from controllers.banking_access import owned_account
from dtos.piggy_bank_dto import PiggyBankDTO, page_envelope
from errors import AccountNotOperational, RequestControlKeyConflict
from errors.piggy_bank_errors import (
    InvalidPiggyBankDate,
    PiggyBankDuplicateName,
    PiggyBankMustBeEmpty,
    PiggyBankNotFound,
    PiggyBankNotOperational,
    PiggyBankVersionConflict,
)
from repositories import AccountRepository
from repositories.piggy_bank_repository import PiggyBankRepository
from utils.identifiers import canonical_uuid
from utils.structured_log import emit_event


class PiggyBankController(BaseController):
    def __init__(self):
        super().__init__(__name__)
        self.accounts = AccountRepository(self.context)
        self.piggies = PiggyBankRepository(self.context)

    @staticmethod
    def _active(account, piggy=None):
        if account.status.enumerator != "active":
            raise AccountNotOperational(account.account_key, account.status.enumerator)
        if piggy is not None and piggy.status != "active":
            raise PiggyBankNotOperational()

    @staticmethod
    def _date(value):
        if value is None:
            return None
        try:
            result = date.fromisoformat(value)
        except ValueError:
            raise InvalidPiggyBankDate() from None
        if result < date.today():
            raise InvalidPiggyBankDate()
        return result

    def _piggy(self, account, key, lock=False):
        piggy = self.piggies.get_by_key(account.id, key, for_update=lock)
        if piggy is None:
            raise PiggyBankNotFound()
        return piggy

    def create(self, account_key, identity, payload):
        account = owned_account(self.accounts, account_key, identity, lock=True)
        key = canonical_uuid(payload["request_control_key"])
        data = {
            "name": " ".join(payload["name"].split()),
            "description": payload.get("description"),
            "target_amount": payload["target_amount"],
            "target_date": payload.get("target_date"),
        }
        if data["description"] is not None:
            data["description"] = data["description"].strip()
        fingerprint = hashlib.sha256(
            json.dumps(
                {**data, "account_key": account.account_key},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        replay = self.piggies.get_by_creation_key(key)
        if replay is not None:
            if (
                replay.account_id != account.id
                or replay.creation_fingerprint != fingerprint
            ):
                raise RequestControlKeyConflict(key)
            return replay.creation_response
        self._active(account)
        name_normalized = data["name"].casefold()
        if self.piggies.get_by_name(account.id, name_normalized):
            raise PiggyBankDuplicateName()
        data["target_date"] = self._date(data["target_date"])
        try:
            piggy = self.piggies.create(
                account_id=account.id,
                creation_request_key=key,
                creation_fingerprint=fingerprint,
                name_normalized=name_normalized,
                version=1,
                balance=0,
                status="active",
                **data,
            )
            response = {"piggy_bank_key": piggy.piggy_bank_key, "version": 1}
            piggy.creation_response = response
            self.piggies.event(
                piggy, "created", {**data, "target_date": payload.get("target_date")}
            )
            self.session.commit()
            emit_event(
                "piggy_bank_created",
                result="committed",
                piggy_bank_key=response["piggy_bank_key"],
            )
            return response
        except IntegrityError as error:
            self.session.rollback()
            if getattr(error.orig, "pgcode", None) == "23505":
                if self.piggies.get_by_creation_key(key):
                    raise RequestControlKeyConflict(key) from None
                raise PiggyBankDuplicateName() from None
            raise

    def get(self, account_key, identity, key):
        account = owned_account(self.accounts, account_key, identity)
        return PiggyBankDTO.obj_to_dict(self._piggy(account, key), account.account_key)

    def list(self, account_key, identity, limit, page, status=None):
        account = owned_account(self.accounts, account_key, identity)
        return page_envelope(
            self.piggies.list_page(account.id, limit, page, status),
            limit,
            page,
            lambda p: PiggyBankDTO.obj_to_dict(p, account.account_key),
        )

    def update(self, account_key, identity, key, payload):
        account = owned_account(self.accounts, account_key, identity, lock=True)
        piggy = self._piggy(account, key, lock=True)
        self._active(account, piggy)
        if payload["expected_version"] != piggy.version:
            raise PiggyBankVersionConflict()
        changes = {}
        for field in ("name", "target_amount", "target_date", "description"):
            if field not in payload:
                continue
            before, after = getattr(piggy, field), payload[field]
            if field == "name":
                after = " ".join(after.split())
                normalized = after.casefold()
                duplicate = self.piggies.get_by_name(account.id, normalized)
                if duplicate is not None and duplicate.id != piggy.id:
                    raise PiggyBankDuplicateName()
                piggy.name_normalized = normalized
            elif field == "target_date":
                after = self._date(after)
            elif field == "description" and after is not None:
                after = after.strip()
            setattr(piggy, field, after)
            changes[field] = {
                "from": before.isoformat() if isinstance(before, date) else before,
                "to": after.isoformat() if isinstance(after, date) else after,
            }
        piggy.version += 1
        self.piggies.event(piggy, "updated", changes)
        self.session.flush()
        response = PiggyBankDTO.obj_to_dict(piggy, account.account_key)
        self.session.commit()
        return response

    def close(self, account_key, identity, key, expected_version):
        account = owned_account(self.accounts, account_key, identity, lock=True)
        piggy = self._piggy(account, key, lock=True)
        if piggy.status == "closed":
            return PiggyBankDTO.obj_to_dict(piggy, account.account_key)
        if expected_version != piggy.version:
            raise PiggyBankVersionConflict()
        if piggy.balance:
            raise PiggyBankMustBeEmpty()
        piggy.status = "closed"
        piggy.version += 1
        self.piggies.event(
            piggy, "closed", {"status": {"from": "active", "to": "closed"}}
        )
        self.session.flush()
        response = PiggyBankDTO.obj_to_dict(piggy, account.account_key)
        self.session.commit()
        return response

    def events(self, account_key, identity, key, limit, page):
        account = owned_account(self.accounts, account_key, identity)
        piggy = self._piggy(account, key)
        return page_envelope(
            self.piggies.list_events(piggy.id, limit, page),
            limit,
            page,
            PiggyBankDTO.event_to_dict,
        )

    def transactions(self, account_key, identity, key, limit, page):
        account = owned_account(self.accounts, account_key, identity)
        piggy = self._piggy(account, key)
        return page_envelope(
            self.piggies.list_transactions(piggy.id, limit, page),
            limit,
            page,
            PiggyBankDTO.statement_item,
        )

    def balances(self, account_key, identity):
        account = owned_account(self.accounts, account_key, identity, lock=True)
        reserved = self.piggies.reserved_balance(account.id)
        return {
            "account_key": account.account_key,
            "available_balance": account.balance,
            "reserved_balance": reserved,
            "total_balance": account.balance + reserved,
            "currency": "BRL",
        }
