from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import calendar
import re
import urllib.request
import xml.etree.ElementTree as ET
from typing import Iterable, List, Tuple

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from .models import Statement, Transaction


CATEGORY_MAP = {
    "Revenue": "revenue_total",
    "Expenses towards government (taxes)": "taxes_total",
    "Expeses for accountant": "accountant_total",
    "Expenses for Car Leasing": "car_leasing_total",
    "Leasing Fuel Expenses": "leasing_fuel_total",
    "Expenses for employees": "employees_total",
    "Paid dividends": "dividends_total",
    "Other expenses": "other_expenses_total",
    "Internal transfer": "transfers_total",
}


def _month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def _parse_month(value: str) -> date:
    value = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}", value):
        return date.fromisoformat(f"{value}-01")
    if re.fullmatch(r"\d{4}", value):
        return date.fromisoformat(f"{value}-01-01")
    raise ValueError(f"Invalid month format: {value}")


_BNR_RATE_CACHE: dict[tuple[date, str], float] = {}


def _fetch_bnr_rate(rate_date: date, currency: str) -> float | None:
    if currency == "RON":
        return 1.0
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


def _build_rate_map(rows: list[Transaction]) -> dict[str, float | None]:
    currencies = {row.account_currency for row in rows}
    rate_map: dict[str, float | None] = {}
    for currency in currencies:
        rate_map[currency] = _fetch_bnr_rate(date.today(), currency)
    return rate_map


def compute_monthly_metrics(
    session: Session,
    *,
    from_month: str,
    to_month: str,
    currency: str,
    use_overrides: bool,
) -> List[dict]:
    query = select(Transaction).join(Statement, Transaction.statement_id == Statement.statement_id)
    query = query.where(Statement.include_in_metrics.is_(True))

    if currency != "all":
        query = query.where(Transaction.account_currency == currency)

    from_date = _parse_month(from_month)
    to_date = _parse_month(to_month)
    last_day = calendar.monthrange(to_date.year, to_date.month)[1]
    to_date = to_date.replace(day=last_day)

    query = query.where(Transaction.txn_date_utc >= from_date, Transaction.txn_date_utc <= to_date)

    rows = session.execute(query).scalars().all()

    def resolve_category(txn: Transaction) -> str:
        if txn.is_internal_transfer:
            return "Internal transfer"
        return txn.category_override if use_overrides and txn.category_override else txn.category

    def effective_amount(txn: Transaction) -> float:
        """Get effective amount, applying amount_override and sign_override."""
        base = float(txn.amount_override) if txn.amount_override is not None else float(txn.amount)
        if txn.sign_override:
            base = -base
        return base

    if currency == "all":
        rate_map = _build_rate_map(rows)
        grouped_by_currency = defaultdict(list)
        for row in rows:
            grouped_by_currency[(row.account_currency, _month_key(row.txn_date_utc))].append(row)

        aggregated = defaultdict(lambda: {
            "totals": defaultdict(float),
            "counts": defaultdict(int),
            "needs_review": 0,
            "transfers_in_ron": 0.0,
            "transfers_out_original": 0.0,  # In original currency (e.g. GBP)
            "transfers_out_currency": None,
        })

        for (currency_key, month), txns in grouped_by_currency.items():
            totals = defaultdict(float)
            counts = defaultdict(int)
            needs_review_count = 0
            transfers_in = 0.0
            transfers_out = 0.0

            for txn in txns:
                category = resolve_category(txn)
                amount_value = effective_amount(txn)
                totals[CATEGORY_MAP[category]] += amount_value
                counts[category] += 1
                if txn.needs_review:
                    needs_review_count += 1
                
                # Track transfers separately
                if txn.is_internal_transfer:
                    if txn.direction == "inflow":
                        transfers_in += abs(amount_value)
                    else:
                        transfers_out += abs(amount_value)

            rate = rate_map.get(currency_key)
            if rate is None:
                continue

            bucket = aggregated[month]
            for key, value in totals.items():
                bucket["totals"][key] += value * rate
            for key, value in counts.items():
                bucket["counts"][key] += value
            bucket["needs_review"] += needs_review_count
            bucket["transfers_in_ron"] += transfers_in * rate
            # Keep transfers_out in original currency (not converted)
            if transfers_out > 0 and currency_key != "RON":
                bucket["transfers_out_original"] += transfers_out
                bucket["transfers_out_currency"] = currency_key

        items: List[dict] = []
        for month in sorted(aggregated.keys()):
            totals = aggregated[month]["totals"]
            counts = aggregated[month]["counts"]
            needs_review_count = aggregated[month]["needs_review"]
            transfers_in_ron = aggregated[month]["transfers_in_ron"]
            transfers_out_original = aggregated[month]["transfers_out_original"]
            transfers_out_currency = aggregated[month]["transfers_out_currency"]

            # Calculate avg FX rate as transfers_in_ron / transfers_out_original
            avg_fx_rate = transfers_in_ron / transfers_out_original if transfers_out_original > 0 else None

            revenue_total = totals["revenue_total"] + transfers_in_ron
            taxes_total = totals["taxes_total"]
            accountant_total = totals["accountant_total"]
            car_leasing_total = totals["car_leasing_total"]
            leasing_fuel_total = totals["leasing_fuel_total"]
            employees_total = totals["employees_total"]
            dividends_total = totals["dividends_total"]
            other_expenses_total = totals["other_expenses_total"]
            transfers_total = totals["transfers_total"]
            # Convert transfers_out to RON for expense calculation
            transfers_out_ron = transfers_out_original * avg_fx_rate if avg_fx_rate and transfers_out_original > 0 else 0.0

            total_expenses_operational = (
                taxes_total
                + accountant_total
                + car_leasing_total
                + leasing_fuel_total
                + employees_total
                + dividends_total
                + other_expenses_total
                + transfers_out_ron
            )
            net_income_operational = revenue_total - total_expenses_operational
            net_cash_after_dividends = revenue_total - total_expenses_operational

            items.append(
                {
                    "month": month,
                    "currency": "RON",
                    "revenue_total": round(revenue_total, 2),
                    "taxes_total": round(taxes_total, 2),
                    "accountant_total": round(accountant_total, 2),
                    "car_leasing_total": round(car_leasing_total, 2),
                    "leasing_fuel_total": round(leasing_fuel_total, 2),
                    "employees_total": round(employees_total, 2),
                    "dividends_total": round(dividends_total, 2),
                    "other_expenses_total": round(other_expenses_total, 2),
                    "transfers_total": round(transfers_total, 2),
                    "transfers_in_ron": round(transfers_in_ron, 2),
                    "transfers_out_original": round(transfers_out_original, 2),
                    "transfers_out_currency": transfers_out_currency,
                    "avg_fx_rate": round(avg_fx_rate, 4) if avg_fx_rate else None,
                    "total_expenses_operational": round(total_expenses_operational, 2),
                    "net_income_operational": round(net_income_operational, 2),
                    "net_cash_after_dividends": round(net_cash_after_dividends, 2),
                    "counts_by_category": dict(counts),
                    "needs_review_count": needs_review_count,
                }
            )
        return items

    grouped = defaultdict(list)
    for row in rows:
        grouped[(row.account_currency, _month_key(row.txn_date_utc))].append(row)

    items: List[dict] = []

    for (currency_key, month), txns in sorted(grouped.items(), key=lambda item: item[0][1]):
        totals = defaultdict(float)
        counts = defaultdict(int)
        needs_review_count = 0
        transfers_in = 0.0
        transfers_out = 0.0
        fx_rates = []

        for txn in txns:
            category = resolve_category(txn)
            amount_value = effective_amount(txn)
            totals[CATEGORY_MAP[category]] += amount_value
            counts[category] += 1
            if txn.needs_review:
                needs_review_count += 1
            
            if txn.is_internal_transfer:
                if txn.direction == "inflow":
                    transfers_in += abs(amount_value)
                else:
                    transfers_out += abs(amount_value)
                if txn.fx_rate_applied:
                    fx_rates.append((abs(amount_value), float(txn.fx_rate_applied)))

        total_weight = sum(w for w, _ in fx_rates)
        avg_fx_rate = sum(w * r for w, r in fx_rates) / total_weight if total_weight > 0 else None

        revenue_total = totals["revenue_total"] + transfers_in
        taxes_total = totals["taxes_total"]
        accountant_total = totals["accountant_total"]
        car_leasing_total = totals["car_leasing_total"]
        leasing_fuel_total = totals["leasing_fuel_total"]
        employees_total = totals["employees_total"]
        dividends_total = totals["dividends_total"]
        other_expenses_total = totals["other_expenses_total"]
        transfers_total = totals["transfers_total"]

        total_expenses_operational = (
            taxes_total
            + accountant_total
            + car_leasing_total
            + leasing_fuel_total
            + employees_total
            + dividends_total
            + other_expenses_total
            + transfers_out
        )
        net_income_operational = revenue_total - total_expenses_operational
        net_cash_after_dividends = revenue_total - total_expenses_operational

        items.append(
            {
                "month": month,
                "currency": currency_key,
                "revenue_total": round(revenue_total, 2),
                "taxes_total": round(taxes_total, 2),
                "accountant_total": round(accountant_total, 2),
                "car_leasing_total": round(car_leasing_total, 2),
                "leasing_fuel_total": round(leasing_fuel_total, 2),
                "employees_total": round(employees_total, 2),
                "dividends_total": round(dividends_total, 2),
                "other_expenses_total": round(other_expenses_total, 2),
                "transfers_total": round(transfers_total, 2),
                "transfers_in": round(transfers_in, 2),
                "transfers_out": round(transfers_out, 2),
                "avg_fx_rate": round(avg_fx_rate, 4) if avg_fx_rate else None,
                "total_expenses_operational": round(total_expenses_operational, 2),
                "net_income_operational": round(net_income_operational, 2),
                "net_cash_after_dividends": round(net_cash_after_dividends, 2),
                "counts_by_category": dict(counts),
                "needs_review_count": needs_review_count,
            }
        )

    return items


def compute_summary(metrics: List[dict]) -> dict:
    totals = defaultdict(float)
    needs_review = 0
    transfers_out_currency = None

    for row in metrics:
        for key in [
            "revenue_total",
            "taxes_total",
            "accountant_total",
            "car_leasing_total",
            "leasing_fuel_total",
            "employees_total",
            "dividends_total",
            "other_expenses_total",
            "transfers_total",
            "total_expenses_operational",
            "net_income_operational",
            "net_cash_after_dividends",
        ]:
            totals[key] += float(row[key])
        
        # Handle transfer fields (different names for currency=all vs single)
        if "transfers_in_ron" in row:
            totals["transfers_in_ron"] += float(row["transfers_in_ron"])
            totals["transfers_out_original"] += float(row.get("transfers_out_original", 0))
            if row.get("transfers_out_currency"):
                transfers_out_currency = row["transfers_out_currency"]
        elif "transfers_in" in row:
            totals["transfers_in"] += float(row["transfers_in"])
            totals["transfers_out"] += float(row["transfers_out"])
        
        needs_review += row["needs_review_count"]

    totals["needs_review_count"] = needs_review
    totals["transfers_out_currency"] = transfers_out_currency
    
    # Calculate overall average FX rate as transfers_in_ron / transfers_out_original
    transfers_out_orig = totals["transfers_out_original"]
    if transfers_out_orig > 0:
        totals["avg_fx_rate"] = round(totals["transfers_in_ron"] / transfers_out_orig, 4)
    else:
        totals["avg_fx_rate"] = None
    
    result = {}
    for key, value in totals.items():
        if key == "needs_review_count":
            result[key] = value
        elif key == "avg_fx_rate":
            result[key] = value
        elif key == "transfers_out_currency":
            result[key] = value
        else:
            result[key] = round(value, 2)
    return result
