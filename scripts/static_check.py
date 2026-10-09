"""Checks rápidos que não precisam de Docker/PostgreSQL."""
from __future__ import annotations

import ast
import json
from collections import defaultdict
from pathlib import Path

from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parents[1]


def check_schemas() -> None:
    for path in (ROOT / "src" / "schemas").glob("*.json"):
        Draft7Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


def check_error_codes() -> None:
    codes = defaultdict(list)
    for path in (ROOT / "src" / "errors").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for statement in node.body:
                if not isinstance(statement, ast.Assign):
                    continue
                if not any(isinstance(target, ast.Name) and target.id == "code" for target in statement.targets):
                    continue
                if isinstance(statement.value, ast.Constant):
                    codes[statement.value.value].append(f"{path.name}:{node.name}")
    duplicates = {code: places for code, places in codes.items() if len(places) > 1}
    assert not duplicates, f"Códigos QIT duplicados: {duplicates}"


def check_black_box_tests() -> None:
    forbidden = ("controllers", "repositories", "models", "resources", "dtos")
    offenders = []
    for path in (ROOT / "tests").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for module in forbidden:
            if f"from {module}" in text or f"import {module}" in text:
                offenders.append(f"{path}: {module}")
    assert not offenders, "Testes de integração importam camadas internas: " + ", ".join(offenders)


def check_resource_raises() -> None:
    offenders = []
    for path in (ROOT / "src" / "resources").glob("*.py"):
        if "raise " in path.read_text(encoding="utf-8"):
            offenders.append(str(path))
    assert not offenders, f"Regra/raise vazou para resources: {offenders}"


if __name__ == "__main__":
    check_schemas()
    check_error_codes()
    check_black_box_tests()
    check_resource_raises()
    print("STATIC_CHECK_OK")
