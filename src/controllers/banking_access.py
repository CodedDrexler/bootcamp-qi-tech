from errors import AccountNotFound, MissingClientIdentity
from utils.identifiers import canonical_uuid


def owned_account(repository, account_key, identity, lock=False):
    identity, key = canonical_uuid(identity), canonical_uuid(account_key)
    if not identity:
        raise MissingClientIdentity()
    account = (
        next(iter(repository.get_many_for_update([key])), None)
        if lock
        else repository.get_by_key(key)
    )
    if account is None or account.client.client_key != identity:
        raise AccountNotFound(key)
    return account
