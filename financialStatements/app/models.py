from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow

CATEGORY_VALUES = (
    "Revenue",
    "Expenses towards government (taxes)",
    "Expeses for accountant",
    "Expenses for Car Leasing",
    "Leasing Fuel Expenses",
    "Expenses for employees",
    "Paid dividends",
    "Other expenses",
)

DIRECTION_VALUES = ("inflow", "outflow", "neutral")


class Statement(Base):
    __tablename__ = "statements"

    statement_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    file_name: Mapped[str] = mapped_column(String(255))
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    pages: Mapped[int] = mapped_column(Integer)
    accounts_found: Mapped[str] = mapped_column(Text, default="[]")
    parse_status: Mapped[str] = mapped_column(String(32), default="success")
    parse_errors: Mapped[str] = mapped_column(Text, default="[]")
    include_in_metrics: Mapped[bool] = mapped_column(Boolean, default=True)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    statement_id: Mapped[str] = mapped_column(String(36), index=True)
    source_file_name: Mapped[str] = mapped_column(String(255))
    account_currency: Mapped[str] = mapped_column(String(8))
    account_name: Mapped[str] = mapped_column(String(128))
    account_iban: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)

    txn_date_utc: Mapped[date] = mapped_column(Date)
    description_raw: Mapped[str] = mapped_column(Text)
    txn_type_code: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    revolut_txn_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    from_account: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    to_account: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    money_out: Mapped[Optional[float]] = mapped_column(Numeric(18, 2), nullable=True)
    money_in: Mapped[Optional[float]] = mapped_column(Numeric(18, 2), nullable=True)
    balance: Mapped[Optional[float]] = mapped_column(Numeric(18, 2), nullable=True)

    direction: Mapped[str] = mapped_column(Enum(*DIRECTION_VALUES, name="direction"))
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    signed_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    category: Mapped[str] = mapped_column(Enum(*CATEGORY_VALUES, name="category"))
    confidence: Mapped[float] = mapped_column(Float)
    category_reason: Mapped[str] = mapped_column(String(255))
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    is_internal_transfer: Mapped[bool] = mapped_column(Boolean, default=False)

    transfer_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    transfer_from_currency: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    transfer_to_currency: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    fx_rate_applied: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fx_rate_official: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fx_loss_ron: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    amount_override: Mapped[Optional[float]] = mapped_column(Numeric(18, 2), nullable=True)
    sign_override: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    category_override: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    override_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
