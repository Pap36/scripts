from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Tuple

from .models import CATEGORY_VALUES

CATEGORY_SET = set(CATEGORY_VALUES)

PRIORITY = [
    "Paid dividends",
    "Expenses towards government (taxes)",
    "Expenses for employees",
    "Expenses for Car Leasing",
    "Leasing Fuel Expenses",
    "Expeses for accountant",
    "Revenue",
    "Other expenses",
]

VENDOR_ACCOUNTANT = ["optimar consult expert"]
VENDOR_CAR_LEASING = ["bcr leasing", "aliat", "roviniete"]


@dataclass
class CategorizationResult:
    category: str
    confidence: float
    reason: str
    needs_review: bool


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(kw in text for kw in keywords)


def _word_boundary(text: str, token: str) -> bool:
    return re.search(rf"\b{re.escape(token)}\b", text) is not None


def categorize(
    *,
    description: str,
    txn_type_code: str | None,
    direction: str,
    to_account: str | None,
    from_account: str | None,
) -> CategorizationResult:
    normalized = _normalize(" ".join([description or "", to_account or "", from_account or ""]))

    def strong(reason: str, category: str) -> CategorizationResult:
        return CategorizationResult(category=category, confidence=0.90, reason=reason, needs_review=False)

    def vendor(reason: str, category: str) -> CategorizationResult:
        return CategorizationResult(category=category, confidence=0.95, reason=reason, needs_review=False)

    def weak(reason: str, category: str) -> CategorizationResult:
        return CategorizationResult(category=category, confidence=0.70, reason=reason, needs_review=False)

    def fallback(reason: str, category: str) -> CategorizationResult:
        return CategorizationResult(category=category, confidence=0.40, reason=reason, needs_review=True)

    if _contains_any(normalized, ["money added"]):
        return strong("money added", "Revenue")

    if direction == "outflow" and _contains_any(normalized, ["dividende", "dividend", "plata dividende", "profit share"]):
        return strong("dividend keyword", "Paid dividends")

    if direction == "outflow" and _contains_any(
        normalized,
        ["trezoreria", "anaf", "impozit", "contributii", "tax"],
    ):
        return strong("tax keyword", "Expenses towards government (taxes)")

    if direction == "outflow" and (
        _word_boundary(normalized, "cam")
        or _word_boundary(normalized, "cass")
        or _word_boundary(normalized, "cas")
    ):
        return weak("tax acronym", "Expenses towards government (taxes)")

    if direction == "outflow" and _contains_any(normalized, ["salariu", "payroll", "wage", "salary", "bonus"]):
        return strong("employee keyword", "Expenses for employees")

    if direction == "outflow" and _word_boundary(normalized, "cim"):
        return weak("cim keyword", "Expenses for employees")

    if direction == "outflow" and _contains_any(normalized, ["mol", "omv"]):
        return strong("fuel keyword", "Leasing Fuel Expenses")

    if direction == "outflow" and _contains_any(normalized, ["leasing"]):
        return strong("leasing keyword", "Expenses for Car Leasing")

    if direction == "outflow" and _contains_any(normalized, VENDOR_CAR_LEASING):
        return vendor("car leasing vendor", "Expenses for Car Leasing")

    if direction == "outflow" and _contains_any(normalized, ["contabil", "contabilitate", "accounting", "expert"]):
        return strong("accounting keyword", "Expeses for accountant")

    if direction == "outflow" and _contains_any(normalized, VENDOR_ACCOUNTANT):
        return vendor("accountant vendor", "Expeses for accountant")

    if direction == "inflow" and (txn_type_code in {"MOA", "MOR"}):
        return strong("inflow type code", "Revenue")

    if direction == "inflow" and _contains_any(normalized, ["money added", "payment received", "incasare", "incasat"]):
        return strong("inflow keyword", "Revenue")

    if direction == "inflow":
        return weak("inflow fallback", "Revenue")

    if direction == "outflow":
        return fallback("outflow fallback", "Other expenses")

    return fallback("neutral fallback", "Other expenses")
