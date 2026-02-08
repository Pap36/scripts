from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class StatementResponse(BaseModel):
    statement_id: str
    imported_at: datetime
    file_name: str
    pages: int
    accounts_found: list
    parse_status: str
    parse_errors: list
    include_in_metrics: bool


class StatementUpdateRequest(BaseModel):
    include_in_metrics: Optional[bool] = None


class StatementsListResponse(BaseModel):
    items: List[StatementResponse]


class TransactionResponse(BaseModel):
    id: str
    statement_id: str
    source_file_name: str
    account_currency: str
    account_name: str
    account_iban: Optional[str]
    period_start: date
    period_end: date
    txn_date_utc: date
    description_raw: str
    txn_type_code: Optional[str]
    revolut_txn_id: Optional[str]
    from_account: Optional[str]
    to_account: Optional[str]
    money_out: Optional[float]
    money_in: Optional[float]
    balance: Optional[float]
    direction: str
    amount: float
    signed_amount: float
    category: str
    confidence: float
    category_reason: str
    needs_review: bool
    is_internal_transfer: bool
    transfer_group_id: Optional[str]
    transfer_from_currency: Optional[str]
    transfer_to_currency: Optional[str]
    fx_rate_applied: Optional[float]
    fx_rate_official: Optional[float]
    fx_loss_ron: Optional[float]
    amount_override: Optional[float]
    sign_override: Optional[bool]
    category_override: Optional[str]
    override_reason: Optional[str]
    created_at: datetime
    updated_at: datetime


class TransactionUpdateRequest(BaseModel):
    category_override: Optional[str] = None
    override_reason: Optional[str] = None
    amount_override: Optional[float] = None
    sign_override: Optional[bool] = None


class TransactionsListResponse(BaseModel):
    items: List[TransactionResponse]
    total: int
    page: int
    page_size: int


class MetricsPoint(BaseModel):
    month: str
    currency: str
    revenue_total: float
    taxes_total: float
    accountant_total: float
    car_leasing_total: float
    leasing_fuel_total: float
    employees_total: float
    dividends_total: float
    other_expenses_total: float
    transfers_total: float
    transfers_in_ron: Optional[float] = None
    transfers_out_original: Optional[float] = None
    transfers_out_currency: Optional[str] = None
    transfers_in: Optional[float] = None
    transfers_out: Optional[float] = None
    avg_fx_rate: Optional[float] = None
    total_expenses_operational: float
    net_income_operational: float
    net_cash_after_dividends: float
    counts_by_category: dict
    needs_review_count: int


class MetricsSeriesResponse(BaseModel):
    items: List[MetricsPoint]


class MetricsSummaryResponse(BaseModel):
    from_month: str
    to_month: str
    currency: str
    totals: dict
