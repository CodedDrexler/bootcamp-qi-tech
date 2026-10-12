def customer_dto(c):
    return {
        "customer_key": c.customer_key,
        "name": c.name,
        "email": c.email,
        "document_number": c.document_number,
        "birthdate": c.birthdate.isoformat(),
        "created_at": c.created_at.isoformat(),
    }


def event_dto(e):
    return {"status": e.status, "event_datetime": e.created_at.isoformat()}


def account_dto(a, customer_key, piggies):
    reserved = sum(p.balance for p in piggies)
    return {
        "account_key": a.account_key,
        "customer_key": customer_key,
        "status": a.status,
        "balance": a.balance,
        "reserved_balance": reserved,
        "total_balance": a.balance + reserved,
        "currency": "BRL",
        "created_at": a.created_at.isoformat(),
    }


def piggy_dto(p, account_key):
    return {
        "piggy_bank_key": p.piggy_bank_key,
        "account_key": account_key,
        "name": p.name,
        "target_amount": p.target_amount,
        "balance": p.balance,
        "status": p.status,
        "goal_reached": p.balance >= p.target_amount,
        "currency": "BRL",
        "created_at": p.created_at.isoformat(),
    }


def transaction_dto(t):
    return {
        "transaction_key": t.transaction_key,
        "type": t.type,
        "amount": t.amount,
        "fee": t.fee,
        "currency": "BRL",
        "created_at": t.created_at.isoformat(),
    }


def entry_dto(row):
    e, transaction_key = row
    return {
        "entry_key": e.entry_key,
        "transaction_key": transaction_key,
        "type": e.type,
        "amount": e.amount,
        "balance_after": e.balance_after,
        "created_at": e.created_at.isoformat(),
    }


def page_dto(items, limit, page, convert):
    return {
        "data": [convert(i) for i in items[:limit]],
        "limit": limit,
        "page": page,
        "is_last_page": len(items) <= limit,
    }
