"""Demonstra o banco pela API; usa dados sintéticos e não zera o banco."""

import json
import os
from uuid import uuid4
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

BASE = os.getenv("BANK_API_URL", f"http://127.0.0.1:{os.getenv('API_PORT', '3000')}")
TOKEN = os.getenv("INTERNAL_TOKEN", "default_token")


def send(method, path, body=None):
    headers = {"INTERNAL-TOKEN": TOKEN, "Idempotency-Key": str(uuid4())}
    r = requests.request(method, BASE + path, json=body, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()


def customer(name):
    digits = [int(c) for c in f"{uuid4().int % 1000000000:09d}"]
    for size in (9, 10):
        d = sum(n * (size + 1 - i) for i, n in enumerate(digits)) * 10 % 11
        digits.append(0 if d == 10 else d)
    s = "".join(map(str, digits))
    c = send(
        "POST",
        "/customers",
        {
            "name": name,
            "document_number": f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}",
            "email": f"{uuid4()}@example.test",
            "birthdate": "1990-01-01",
        },
    )
    return send("POST", "/accounts", c)["account_key"]


def main():
    a, b = customer("Cliente de demonstração A"), customer("Cliente de demonstração B")
    send("POST", f"/accounts/{a}/transactions", {"type": "DEPOSIT", "amount": 10000})
    p = send(
        "POST", f"/accounts/{a}/piggy_banks", {"name": "Viagem", "target_amount": 4000}
    )["piggy_bank_key"]
    route = f"/accounts/{a}/piggy_banks/{p}"
    send("POST", route + "/transactions", {"type": "SAVE", "amount": 4000})
    send(
        "POST",
        f"/accounts/{a}/transactions",
        {"type": "TRANSFER", "amount": 2500, "destination_account_key": b},
    )
    summary = {
        "conta_A": send("GET", f"/accounts/{a}"),
        "conta_B": send("GET", f"/accounts/{b}"),
        "porquinho": send("GET", route),
        "extrato_A": send("GET", f"/accounts/{a}/transactions"),
    }
    assert summary["conta_A"]["balance"] == 3400
    assert summary["conta_A"]["reserved_balance"] == 4000
    assert summary["conta_B"]["balance"] == 2500
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
