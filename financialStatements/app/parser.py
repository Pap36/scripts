from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable, List, Optional

import pdfplumber
from dateutil import parser as date_parser

DATE_LINE = re.compile(r"^(\d{1,2})\s+([A-Za-z]{3,4})\s+(\d{4})\s+")

AMOUNT_PATTERN = re.compile(
    r"(?P<currency>[A-Z]{3}|£|€|\$)?\s*(?P<amount>\d{1,3}(?:[\s,]\d{3})*(?:\.\d{2})|\d+\.\d{2})"
)

ACCOUNT_NAME_PATTERN = re.compile(r"Account name\s+(.+)$", re.IGNORECASE)
CURRENCY_PATTERN = re.compile(r"Currency\s+([A-Z]{3})", re.IGNORECASE)
IBAN_PATTERN = re.compile(r"IBAN\s*([A-Z0-9 ]+)", re.IGNORECASE)

TRANSACTIONS_FROM_PATTERN = re.compile(r"Transactions from (.+) to (.+)")
HEADER_PATTERN = re.compile(r"Date \(UTC\)\s+Description\s+Money out\s+Money in\s+Balance")

ID_PATTERN = re.compile(r"ID:\s*([0-9a-f-]{16,})", re.IGNORECASE)
TO_ACCOUNT_PATTERN = re.compile(r"To account:\s*([A-Z0-9]+)")
FROM_ACCOUNT_PATTERN = re.compile(r"From account:\s*([A-Z0-9]+)")
TRANSFER_CURRENCY_PATTERN = re.compile(r"\b([A-Z]{3})\s*[–-]>\s*.*?\b([A-Z]{3})\b", re.DOTALL)
FX_RATE_PATTERN = re.compile(r"FX Rate\s+([A-Z]{3})\s+1\s*=\s*([A-Z]{3})\s*([0-9.,]+)")
FX_RATE_LINE_PATTERN = re.compile(r"FX Rate.*", re.IGNORECASE)


@dataclass
class AccountBlock:
    account_name: str
    account_currency: str
    account_iban: Optional[str]
    period_start: date
    period_end: date
    lines: List[str]


@dataclass
class ParsedTransaction:
    txn_date_utc: date
    description_raw: str
    txn_type_code: Optional[str]
    revolut_txn_id: Optional[str]
    from_account: Optional[str]
    to_account: Optional[str]
    money_out: Optional[Decimal]
    money_in: Optional[Decimal]
    balance: Optional[Decimal]
    direction: str
    amount: Decimal
    signed_amount: Decimal
    transfer_from_currency: Optional[str]
    transfer_to_currency: Optional[str]
    fx_rate_applied: Optional[Decimal]


def _parse_date(text: str) -> date:
    return date_parser.parse(text, dayfirst=True).date()


def _normalize_lines(lines: Iterable[str]) -> List[str]:
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        cleaned.append(re.sub(r"\s+", " ", line))
    return cleaned


def _extract_amounts(text: str) -> List[Decimal]:
    amounts = []
    for match in AMOUNT_PATTERN.finditer(text):
        raw = match.group("amount")
        raw = raw.replace(" ", "").replace(",", "")
        try:
            amounts.append(Decimal(raw))
        except Exception:
            continue
    return amounts


def _detect_direction(text: str) -> str:
    normalized = text.lower()
    if any(token in normalized for token in ["payment received", "money added", "incas", "received"]):
        return "inflow"
    return "outflow"


def _parse_transaction_chunk(chunk: str) -> ParsedTransaction:
    lines = chunk.split("\n")
    first_line = lines[0]
    match = DATE_LINE.match(first_line)
    if not match:
        raise ValueError("Chunk does not start with date")

    txn_date = _parse_date(" ".join(match.groups()))

    tokens = first_line.split(" ")
    txn_type_code = tokens[3] if len(tokens) > 3 and tokens[3].isalpha() else None

    revolut_txn_id = None
    to_account = None
    from_account = None

    revolut_match = ID_PATTERN.search(chunk)
    if revolut_match:
        revolut_txn_id = revolut_match.group(1)

    to_match = TO_ACCOUNT_PATTERN.search(chunk)
    if to_match:
        to_account = to_match.group(1)

    from_match = FROM_ACCOUNT_PATTERN.search(chunk)
    if from_match:
        from_account = from_match.group(1)

    description = chunk
    description = FX_RATE_LINE_PATTERN.sub("", description)
    description = ID_PATTERN.sub("", description)
    description = TO_ACCOUNT_PATTERN.sub("", description)
    description = FROM_ACCOUNT_PATTERN.sub("", description)
    description = re.sub(r"\s+", " ", description).strip()

    amounts = _extract_amounts(first_line)
    money_out = None
    money_in = None
    balance = None

    transfer_from_currency = None
    transfer_to_currency = None
    transfer_match = TRANSFER_CURRENCY_PATTERN.search(chunk)
    if transfer_match:
        transfer_from_currency = transfer_match.group(1)
        transfer_to_currency = transfer_match.group(2)

    fx_rate_applied = None
    fx_match = FX_RATE_PATTERN.search(chunk)
    if fx_match:
        base_currency = fx_match.group(1)
        quote_currency = fx_match.group(2)
        raw_rate = fx_match.group(3).replace(",", "")
        try:
            rate_value = Decimal(raw_rate)
            if base_currency == "GBP" and quote_currency == "RON":
                fx_rate_applied = rate_value
            elif base_currency == "RON" and quote_currency == "GBP" and rate_value != 0:
                fx_rate_applied = Decimal("1") / rate_value
        except Exception:
            fx_rate_applied = None

    if amounts:
        balance = amounts[-1] if len(amounts) >= 2 else None
        if len(amounts) >= 2:
            primary_amount = amounts[-2]
            if txn_type_code == "EXI":
                money_in = primary_amount
            elif txn_type_code == "EXO":
                money_out = primary_amount
            else:
                if _detect_direction(chunk) == "inflow":
                    money_in = primary_amount
                else:
                    money_out = primary_amount
        elif len(amounts) == 1:
            if _detect_direction(chunk) == "inflow":
                money_in = amounts[0]
            else:
                money_out = amounts[0]

    if txn_type_code == "EXI":
        direction = "inflow"
    elif txn_type_code == "EXO":
        direction = "outflow"
    elif money_in is not None:
        direction = "inflow"
    elif money_out is not None:
        direction = "outflow"
    else:
        direction = "neutral"

    if money_in is not None:
        amount = money_in
        signed_amount = money_in
    elif money_out is not None:
        amount = money_out
        signed_amount = money_out * Decimal("-1")
    else:
        amount = Decimal("0")
        signed_amount = Decimal("0")

    return ParsedTransaction(
        txn_date_utc=txn_date,
        description_raw=description,
        txn_type_code=txn_type_code,
        revolut_txn_id=revolut_txn_id,
        from_account=from_account,
        to_account=to_account,
        money_out=money_out,
        money_in=money_in,
        balance=balance,
        direction=direction,
        amount=amount,
        signed_amount=signed_amount,
        transfer_from_currency=transfer_from_currency,
        transfer_to_currency=transfer_to_currency,
        fx_rate_applied=fx_rate_applied,
    )


def _split_transactions(lines: List[str]) -> List[str]:
    chunks: List[List[str]] = []
    current: List[str] = []

    for line in lines:
        if DATE_LINE.match(line):
            if current:
                chunks.append(current)
            current = [line]
        else:
            if current:
                current.append(line)
    if current:
        chunks.append(current)

    return ["\n".join(chunk) for chunk in chunks]


def parse_pdf(path: Path) -> dict:
    with path.open("rb") as handle:
        data = handle.read()
    file_hash = hashlib.sha256(data).hexdigest()

    with pdfplumber.open(path) as pdf:
        all_text = []
        for page in pdf.pages:
            text = page.extract_text() or ""
            all_text.append(text)

    lines = _normalize_lines("\n".join(all_text).splitlines())

    account_blocks: List[AccountBlock] = []
    current_account_name = None
    current_currency = None
    current_iban = None
    current_period_start = None
    current_period_end = None
    collecting = False
    collected_lines: List[str] = []

    for line in lines:
        name_match = ACCOUNT_NAME_PATTERN.search(line)
        if name_match:
            current_account_name = name_match.group(1).strip()
            continue

        currency_match = CURRENCY_PATTERN.search(line)
        if currency_match:
            current_currency = currency_match.group(1)
            continue

        iban_match = IBAN_PATTERN.search(line)
        if iban_match:
            current_iban = iban_match.group(1).replace(" ", "")

        period_match = TRANSACTIONS_FROM_PATTERN.search(line)
        if period_match:
            current_period_start = _parse_date(period_match.group(1))
            current_period_end = _parse_date(period_match.group(2))
            collecting = False
            collected_lines = []

        if HEADER_PATTERN.search(line):
            collecting = True
            continue

        if collecting:
            if line.startswith("Account statement") or line.startswith("Transaction types"):
                collecting = False
                if current_account_name and current_currency and current_period_start and current_period_end:
                    account_blocks.append(
                        AccountBlock(
                            account_name=current_account_name,
                            account_currency=current_currency,
                            account_iban=current_iban,
                            period_start=current_period_start,
                            period_end=current_period_end,
                            lines=collected_lines,
                        )
                    )
                collected_lines = []
                continue
            collected_lines.append(line)

    if collecting and current_account_name and current_currency and current_period_start and current_period_end:
        account_blocks.append(
            AccountBlock(
                account_name=current_account_name,
                account_currency=current_currency,
                account_iban=current_iban,
                period_start=current_period_start,
                period_end=current_period_end,
                lines=collected_lines,
            )
        )

    transactions: List[dict] = []
    parse_errors: List[str] = []

    for block in account_blocks:
        chunks = _split_transactions(block.lines)
        for chunk in chunks:
            try:
                parsed = _parse_transaction_chunk(chunk)
                transactions.append(
                    {
                        "account_name": block.account_name,
                        "account_currency": block.account_currency,
                        "account_iban": block.account_iban,
                        "period_start": block.period_start,
                        "period_end": block.period_end,
                        **parsed.__dict__,
                    }
                )
            except Exception as exc:
                parse_errors.append(f"{block.account_currency}: {exc}")

    return {
        "file_hash": file_hash,
        "pages": len(all_text),
        "accounts_found": json.dumps(
            [
                {
                    "account_name": block.account_name,
                    "account_currency": block.account_currency,
                    "account_iban": block.account_iban,
                    "period_start": block.period_start.isoformat(),
                    "period_end": block.period_end.isoformat(),
                }
                for block in account_blocks
            ]
        ),
        "transactions": transactions,
        "parse_errors": json.dumps(parse_errors),
        "parse_status": "partial" if parse_errors else "success",
    }
