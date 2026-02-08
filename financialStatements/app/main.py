from __future__ import annotations

import json
import calendar
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .categorizer import categorize
from .db import Base, ENGINE, ensure_schema, get_session
from .metrics import compute_monthly_metrics, compute_summary
from .models import Statement, Transaction
from .parser import parse_pdf
from .schemas import (
    MetricsSeriesResponse,
    MetricsSummaryResponse,
    StatementResponse,
    StatementUpdateRequest,
    StatementsListResponse,
    TransactionResponse,
    TransactionUpdateRequest,
    TransactionsListResponse,
)

app = FastAPI(title="Financial Statements API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=ENGINE)
ensure_schema()

UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_BNR_RATE_CACHE: dict[tuple[date, str], float] = {}


def _fetch_bnr_rate(rate_date: date, currency: str) -> float | None:
    cache_key = (rate_date, currency)
    if cache_key in _BNR_RATE_CACHE:
        return _BNR_RATE_CACHE[cache_key]

    for offset in range(0, 10):
        lookup_date = rate_date - timedelta(days=offset)
        url = f"https://www.bnr.ro/nbrfxrates.xml?date={lookup_date.isoformat()}"
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                xml_content = response.read()
            root = ET.fromstring(xml_content)
            for rate in root.findall(".//{http://www.bnr.ro/xsd}Rate"):
                if rate.attrib.get("currency") == currency:
                    value = float(rate.text.strip())
                    _BNR_RATE_CACHE[cache_key] = value
                    return value
        except Exception:
            continue
    return None


def _postprocess_transfers(session: Session, statement_id: str) -> None:
    rows = (
        session.execute(
            select(Transaction).where(
                Transaction.statement_id == statement_id, Transaction.txn_type_code.in_(["EXI", "EXO"])
            )
        )
        .scalars()
        .all()
    )

    for txn in rows:
        txn.transfer_group_id = txn.revolut_txn_id or txn.id

    exo_gbp = [t for t in rows if t.txn_type_code == "EXO" and t.account_currency == "GBP" and t.money_out is not None]
    exi_ron = [t for t in rows if t.txn_type_code == "EXI" and t.account_currency == "RON" and t.money_in is not None]

    used_exi: set[str] = set()

    for exo in exo_gbp:
        candidates = [t for t in exi_ron if t.id not in used_exi and t.txn_date_utc == exo.txn_date_utc]
        if not candidates:
            continue

        applied_rate = exo.fx_rate_applied
        if applied_rate is None:
            applied_rate = next((t.fx_rate_applied for t in candidates if t.fx_rate_applied is not None), None)
        if applied_rate is None:
            continue

        expected_ron = float(exo.money_out) * float(applied_rate)
        best = min(candidates, key=lambda t: abs(float(t.money_in) - expected_ron))
        if abs(float(best.money_in) - expected_ron) > 5:
            continue

        used_exi.add(best.id)
        group_id = exo.revolut_txn_id or best.revolut_txn_id or exo.id
        exo.transfer_group_id = group_id
        best.transfer_group_id = group_id

        official_rate = _fetch_bnr_rate(exo.txn_date_utc, "GBP")
        if official_rate is None:
            continue

        gbp_amount = float(exo.money_out)
        ron_amount = float(best.money_in)
        loss_ron = (official_rate * gbp_amount) - ron_amount

        for txn in (exo, best):
            txn.fx_rate_official = official_rate
            txn.fx_rate_applied = float(applied_rate)
            txn.fx_loss_ron = loss_ron


def _parse_month(value: str) -> date:
    value = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}", value):
        return date.fromisoformat(f"{value}-01")
    if re.fullmatch(r"\d{4}", value):
        return date.fromisoformat(f"{value}-01-01")
    raise ValueError(f"Invalid month format: {value}")


def _serialize_statement(statement: Statement) -> StatementResponse:
    return StatementResponse(
        statement_id=statement.statement_id,
        imported_at=statement.imported_at,
        file_name=statement.file_name,
        pages=statement.pages,
        accounts_found=json.loads(statement.accounts_found or "[]"),
        parse_status=statement.parse_status,
        parse_errors=json.loads(statement.parse_errors or "[]"),
        include_in_metrics=statement.include_in_metrics,
    )


def _serialize_transaction(txn: Transaction) -> TransactionResponse:
    def round2(value: float | None) -> float | None:
        return round(value, 2) if value is not None else None

    def round4(value: float | None) -> float | None:
        return round(value, 4) if value is not None else None

    return TransactionResponse(
        id=txn.id,
        statement_id=txn.statement_id,
        source_file_name=txn.source_file_name,
        account_currency=txn.account_currency,
        account_name=txn.account_name,
        account_iban=txn.account_iban,
        period_start=txn.period_start,
        period_end=txn.period_end,
        txn_date_utc=txn.txn_date_utc,
        description_raw=txn.description_raw,
        txn_type_code=txn.txn_type_code,
        revolut_txn_id=txn.revolut_txn_id,
        from_account=txn.from_account,
        to_account=txn.to_account,
        money_out=round2(float(txn.money_out)) if txn.money_out is not None else None,
        money_in=round2(float(txn.money_in)) if txn.money_in is not None else None,
        balance=round2(float(txn.balance)) if txn.balance is not None else None,
        direction=txn.direction,
        amount=round2(float(txn.amount)),
        signed_amount=round2(float(txn.signed_amount)),
        category=txn.category_override or txn.category,
        confidence=txn.confidence,
        category_reason=txn.category_reason,
        needs_review=txn.needs_review,
        is_internal_transfer=txn.is_internal_transfer,
        transfer_group_id=txn.transfer_group_id,
        transfer_from_currency=txn.transfer_from_currency,
        transfer_to_currency=txn.transfer_to_currency,
        fx_rate_applied=round4(txn.fx_rate_applied),
        fx_rate_official=round4(txn.fx_rate_official),
        fx_loss_ron=round2(txn.fx_loss_ron),
        amount_override=round2(float(txn.amount_override)) if txn.amount_override is not None else None,
        sign_override=txn.sign_override,
        category_override=txn.category_override,
        override_reason=txn.override_reason,
        created_at=txn.created_at,
        updated_at=txn.updated_at,
    )


@app.post("/api/statements/upload", response_model=StatementResponse)
async def upload_statement(file: UploadFile = File(...), session: Session = Depends(get_session)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    tmp_path = UPLOAD_DIR / file.filename
    tmp_path.write_bytes(content)

    parse_result = parse_pdf(tmp_path)

    existing = session.execute(select(Statement).where(Statement.file_hash == parse_result["file_hash"]))
    existing_statement = existing.scalar_one_or_none()
    if existing_statement:
        return _serialize_statement(existing_statement)

    statement = Statement(
        file_name=file.filename,
        file_hash=parse_result["file_hash"],
        pages=parse_result["pages"],
        accounts_found=parse_result["accounts_found"],
        parse_status=parse_result["parse_status"],
        parse_errors=parse_result["parse_errors"],
        include_in_metrics=True,
    )

    session.add(statement)
    session.flush()

    for txn_data in parse_result["transactions"]:
        is_internal_transfer = txn_data.get("txn_type_code") in {"EXI", "EXO"}
        direction = txn_data["direction"]

        categorization = categorize(
            description=txn_data["description_raw"],
            txn_type_code=txn_data.get("txn_type_code"),
            direction=direction,
            to_account=txn_data.get("to_account"),
            from_account=txn_data.get("from_account"),
        )

        if is_internal_transfer:
            categorization.category = "Other expenses"

        transaction = Transaction(
            statement_id=statement.statement_id,
            source_file_name=file.filename,
            account_currency=txn_data["account_currency"],
            account_name=txn_data["account_name"],
            account_iban=txn_data["account_iban"],
            period_start=txn_data["period_start"],
            period_end=txn_data["period_end"],
            txn_date_utc=txn_data["txn_date_utc"],
            description_raw=txn_data["description_raw"],
            txn_type_code=txn_data.get("txn_type_code"),
            revolut_txn_id=txn_data.get("revolut_txn_id"),
            from_account=txn_data.get("from_account"),
            to_account=txn_data.get("to_account"),
            money_out=float(txn_data["money_out"]) if txn_data["money_out"] is not None else None,
            money_in=float(txn_data["money_in"]) if txn_data["money_in"] is not None else None,
            balance=float(txn_data["balance"]) if txn_data["balance"] is not None else None,
            direction=direction,
            amount=float(txn_data["amount"]),
            signed_amount=float(txn_data["signed_amount"]),
            category=categorization.category,
            confidence=categorization.confidence,
            category_reason=categorization.reason,
            needs_review=categorization.needs_review,
            is_internal_transfer=is_internal_transfer,
            transfer_from_currency=txn_data.get("transfer_from_currency"),
            transfer_to_currency=txn_data.get("transfer_to_currency"),
            fx_rate_applied=float(txn_data["fx_rate_applied"]) if txn_data.get("fx_rate_applied") is not None else None,
        )

        session.add(transaction)

    session.flush()
    _postprocess_transfers(session, statement.statement_id)
    session.commit()
    return _serialize_statement(statement)


@app.get("/api/statements", response_model=StatementsListResponse)
async def list_statements(session: Session = Depends(get_session)):
    items = session.execute(select(Statement).order_by(Statement.imported_at.desc())).scalars().all()
    return StatementsListResponse(items=[_serialize_statement(item) for item in items])


@app.patch("/api/statements/{statement_id}", response_model=StatementResponse)
async def update_statement(
    statement_id: str,
    payload: StatementUpdateRequest,
    session: Session = Depends(get_session),
):
    statement = session.get(Statement, statement_id)
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")

    fields_set = payload.model_fields_set
    if "include_in_metrics" in fields_set and payload.include_in_metrics is not None:
        statement.include_in_metrics = payload.include_in_metrics

    session.commit()
    session.refresh(statement)
    return _serialize_statement(statement)


@app.post("/api/statements/reparse/{statement_id}", response_model=StatementResponse)
async def reparse_statement(statement_id: str, session: Session = Depends(get_session)):
    statement = session.get(Statement, statement_id)
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")

    file_path = UPLOAD_DIR / statement.file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Stored PDF not found")

    parse_result = parse_pdf(file_path)
    statement.pages = parse_result["pages"]
    statement.accounts_found = parse_result["accounts_found"]
    statement.parse_status = parse_result["parse_status"]
    statement.parse_errors = parse_result["parse_errors"]

    session.execute(delete(Transaction).where(Transaction.statement_id == statement_id))

    for txn_data in parse_result["transactions"]:
        is_internal_transfer = txn_data.get("txn_type_code") in {"EXI", "EXO"}
        direction = txn_data["direction"]
        categorization = categorize(
            description=txn_data["description_raw"],
            txn_type_code=txn_data.get("txn_type_code"),
            direction=direction,
            to_account=txn_data.get("to_account"),
            from_account=txn_data.get("from_account"),
        )
        if is_internal_transfer:
            categorization.category = "Other expenses"
        transaction = Transaction(
            statement_id=statement.statement_id,
            source_file_name=statement.file_name,
            account_currency=txn_data["account_currency"],
            account_name=txn_data["account_name"],
            account_iban=txn_data["account_iban"],
            period_start=txn_data["period_start"],
            period_end=txn_data["period_end"],
            txn_date_utc=txn_data["txn_date_utc"],
            description_raw=txn_data["description_raw"],
            txn_type_code=txn_data.get("txn_type_code"),
            revolut_txn_id=txn_data.get("revolut_txn_id"),
            from_account=txn_data.get("from_account"),
            to_account=txn_data.get("to_account"),
            money_out=float(txn_data["money_out"]) if txn_data["money_out"] is not None else None,
            money_in=float(txn_data["money_in"]) if txn_data["money_in"] is not None else None,
            balance=float(txn_data["balance"]) if txn_data["balance"] is not None else None,
            direction=direction,
            amount=float(txn_data["amount"]),
            signed_amount=float(txn_data["signed_amount"]),
            category=categorization.category,
            confidence=categorization.confidence,
            category_reason=categorization.reason,
            needs_review=categorization.needs_review,
            is_internal_transfer=is_internal_transfer,
            transfer_from_currency=txn_data.get("transfer_from_currency"),
            transfer_to_currency=txn_data.get("transfer_to_currency"),
            fx_rate_applied=float(txn_data["fx_rate_applied"]) if txn_data.get("fx_rate_applied") is not None else None,
        )
        session.add(transaction)

    session.flush()
    _postprocess_transfers(session, statement.statement_id)
    session.commit()
    return _serialize_statement(statement)


@app.get("/api/transactions", response_model=TransactionsListResponse)
async def get_transactions(
    month: str | None = None,
    currency: str | None = None,
    category: str | None = None,
    needs_review: bool | None = None,
    statement_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
    session: Session = Depends(get_session),
):
    query = select(Transaction)

    if month:
        start = _parse_month(month)
        last_day = calendar.monthrange(start.year, start.month)[1]
        end = start.replace(day=last_day)
        query = query.where(Transaction.txn_date_utc >= start, Transaction.txn_date_utc <= end)

    if currency:
        query = query.where(Transaction.account_currency == currency)

    if category:
        query = query.where(Transaction.category == category)

    if needs_review is not None:
        query = query.where(Transaction.needs_review.is_(needs_review))

    if statement_id:
        query = query.where(Transaction.statement_id == statement_id)

    total = session.execute(query).scalars().all()
    total_count = len(total)

    items = (
        session.execute(query.order_by(Transaction.txn_date_utc.desc()).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )

    return TransactionsListResponse(
        items=[_serialize_transaction(item) for item in items],
        total=total_count,
        page=page,
        page_size=page_size,
    )


@app.patch("/api/transactions/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: str,
    payload: TransactionUpdateRequest,
    session: Session = Depends(get_session),
):
    txn = session.get(Transaction, transaction_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    fields_set = payload.model_fields_set
    if "category_override" in fields_set:
        txn.category_override = payload.category_override
    if "override_reason" in fields_set:
        txn.override_reason = payload.override_reason
    if "amount_override" in fields_set:
        txn.amount_override = payload.amount_override
    if "sign_override" in fields_set:
        txn.sign_override = payload.sign_override
    session.commit()
    session.refresh(txn)

    return _serialize_transaction(txn)


@app.get("/api/metrics/monthly", response_model=MetricsSeriesResponse)
async def metrics_monthly(
    from_month: str,
    to_month: str,
    currency: str = "all",
    use_overrides: bool = True,
    session: Session = Depends(get_session),
):
    try:
        items = compute_monthly_metrics(
            session,
            from_month=from_month,
            to_month=to_month,
            currency=currency,
            use_overrides=use_overrides,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return MetricsSeriesResponse(items=items)


@app.get("/api/metrics/summary", response_model=MetricsSummaryResponse)
async def metrics_summary(
    from_month: str,
    to_month: str,
    currency: str = "all",
    use_overrides: bool = True,
    session: Session = Depends(get_session),
):
    try:
        items = compute_monthly_metrics(
            session,
            from_month=from_month,
            to_month=to_month,
            currency=currency,
            use_overrides=use_overrides,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    totals = compute_summary(items)
    return MetricsSummaryResponse(from_month=from_month, to_month=to_month, currency=currency, totals=totals)
