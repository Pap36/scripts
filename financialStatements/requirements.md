# requirements.md — Financial Statement (PDF) Parser + Categorizer + Metrics UI

## 0) Context & fixed assumptions

We will parse **Revolut-style account statements** in PDF format, like the sample provided. :contentReference[oaicite:0]{index=0}

**Key assumption:** all PDFs follow the same structure and contain a **text layer** (so **NO OCR** is required).

A single PDF may contain **multiple currencies/accounts** (e.g., GBP + RON), each with:
- Header metadata (account name, currency, IBAN, etc.)
- A *Balance summary* block (opening balance, money in/out, closing balance)
- A *Transactions from … to …* section with a tabular list:
  - Columns: `Date (UTC)`, `Description`, `Money out`, `Money in`, `Balance`
  - Each transaction spans **multiple wrapped lines** (description + ID + optional “To account / From account”)
- A *Transaction types* summary block (CAR/MOS/EXI/EXO/… with totals)

## 1) Goals

1. Ingest one or more statement PDFs.
2. Extract all transactions reliably.
3. Categorize each transaction into exactly one of:
   1) Revenue  
   2) Expenses towards government (taxes)  
   3) Expeses for accountant  
   4) Expenses for Car Leasing  
   5) Expenses for employees  
   6) Paid dividends  
   7) Other expenses  
4. Compute monthly metrics and visualise them in a UI (graphs + tables), including drilldowns.

## 2) Recommended architecture (pragmatic + implementable)

### Backend: Python (FastAPI) + PDF text parsing
Why:
- Python has mature PDF text extraction (`pdfplumber`) and strong data tooling (`pandas`).
- Easy to expose a clean API for a React dashboard.

### Frontend: React (Vite) + charting (Recharts or Plotly)
Why:
- Quick dashboard iteration.
- Responsive graphs, filters, drilldowns.

### Storage: SQLite (dev) → Postgres (prod)
Store:
- PDFs metadata
- Parsed transactions
- Categorization results and overrides (manual review)
- Aggregations (optional caching)

## 3) Data model (source of truth)

### 3.1 Transaction record (DB + API schema)

Each parsed transaction must produce:

- `id` (uuid)
- `statement_id` (uuid)
- `source_file_name` (string)
- `account_currency` (string; e.g., "RON", "GBP")
- `account_name` (string; e.g., "Main")
- `account_iban` (string|null)
- `period_start` (date)
- `period_end` (date)

- `txn_date_utc` (date; ISO `YYYY-MM-DD`)
- `description_raw` (string; multi-line collapsed to single string)
- `txn_type_code` (enum|string|null)  
  Expected from Revolut format: `CAR`, `MOS`, `MOA`, `MOR`, `ATM`, `EXO`, `EXI`, `FEE` (and future codes)
- `revolut_txn_id` (string|null) extracted from `ID: <uuid-like>`
- `from_account` (string|null)
- `to_account` (string|null)

- `money_out` (Decimal|null)
- `money_in` (Decimal|null)
- `balance` (Decimal|null)

Derived fields:
- `direction` (enum: `inflow|outflow|neutral`)
- `amount` (Decimal; **positive number** always)
- `signed_amount` (Decimal; inflow positive, outflow negative, neutral 0)
- `category` (enum of the 7 categories)
- `confidence` (float 0–1)
- `category_reason` (string; short explanation)
- `needs_review` (bool)
- `is_internal_transfer` (bool; important for FX exchanges)
- `created_at`, `updated_at`

### 3.2 Statement record
- `statement_id`
- `imported_at`
- `hash` (for idempotency; e.g., SHA256 of bytes)
- `pages`
- `accounts_found` (json array with currency/account blocks)
- `parse_status` (success/partial/fail)
- `parse_errors` (json)

## 4) Parsing requirements (Revolut-like PDF)

### 4.1 Extraction approach
- Use `pdfplumber` to extract page text (`page.extract_text()`).
- Do not rely on visual table detection; instead parse via **text patterns** since the format is consistent.

### 4.2 Identify account blocks
A PDF can contain multiple account sections (e.g., GBP section on page 1, RON section on pages 3–4).

An “account block” starts when we detect (regex/pattern):
- `Account name` line
- followed by `Currency <CODE>`

Capture:
- `account_name`
- `account_currency`
- `IBAN` (first matching `IBAN <...>`)
- (optional) Sort code / account number if present

### 4.3 Identify statement period
Parse:
- `Transactions from <D> to <D>` where D includes month names.
Convert to ISO dates.

### 4.4 Identify the transaction table region
Within each account block:
- Find the line `Transactions from ...`
- Then find the header line containing:
  - `Date (UTC) Description Money out Money in Balance`
- All subsequent lines until either:
  - `Account statement` OR
  - `Transaction types` OR
  - end of block/page(s)

### 4.5 Transaction row segmentation (critical)
Each transaction begins with a date at line start, e.g.:
- `27 Jan 2026 ...`
- `6 Jan 2026 ...`

**Rule:** Start a new transaction when a line matches:
- `^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s+`

Then accumulate subsequent lines into the same transaction until next date-start line or end of section.

### 4.6 Field parsing within a transaction chunk
From the concatenated chunk:
- `txn_date_utc`: parse from first 3 tokens (DD Mon YYYY)
- `txn_type_code`: the token after date, commonly `CAR|MOS|MOA|MOR|EXI|EXO|ATM|FEE`  
  Example: `20 Jan 2026 MOS To ...`
- `description_raw`: everything after the type code, excluding structured lines like `ID:`, `To account:`, `From account:`
- `revolut_txn_id`: extract `ID:\s*([0-9a-f-]{16,})`
- `to_account`: extract `To account:\s*([A-Z0-9]+)`
- `from_account`: extract `From account:\s*([A-Z0-9]+)`

Amounts:
- Parse **Money out**, **Money in**, and **Balance** from the *first line of the chunk* if present,
  but note that the PDF text may shift amounts to later tokens.
- Implement robust parsing by scanning the whole chunk for currency amounts:
  - Currency format examples in sample:
    - `10 778.00 RON`
    - `£4 138.00`
    - `- 5 000.00` in summaries (but transaction lines show positive in out column)
- Prefer extracting from the table line pattern:
  - `<date> <type> <desc...> <money_out?> <money_in?> <balance>`
- If not reliably parseable from token positions, use heuristics:
  - Find the **last** amount in the chunk as `balance`
  - Find the **first** amount after description as either `money_out` or `money_in` depending on whether it appears under outflow/inflow pattern for that row.
  - If both appear, assign accordingly.

Direction:
- If `money_in` present -> `direction=inflow`
- Else if `money_out` present -> `direction=outflow`
- Else `direction=neutral` and mark `needs_review=true`

### 4.7 Currency parsing
- Currency is inferred primarily from the **account block currency**.
- If amounts show explicit currency markers (RON, £), store them too; if mismatch, flag review.

### 4.8 “Transaction types” summary parsing (optional)
Parse totals per type code from:
- `Transaction types` section
This is optional but useful for reconciliation.

## 5) Categorization requirements (rule-based, deterministic)

### 5.1 Required categories (exact strings)
1. Revenue
2. Expenses towards government (taxes)
3. Expeses for accountant
4. Expenses for Car Leasing
5. Expenses for employees
6. Paid dividends
7. Other expenses

### 5.2 Internal transfers / FX exchanges
In Revolut statements, FX exchange rows appear as:
- `EXI Main · GBP –> Main · RON`
- `EXO Main · GBP –> Main · RON`

These are **internal transfers** and should NOT count as revenue/expense for P&L-style metrics.

**Implementation requirement:**
- If `txn_type_code` in `{EXI, EXO}`:
  - Set `is_internal_transfer=true`
  - Set `category="Other expenses"` (since category set is fixed)
  - Exclude them from “operational” metrics by default (see §6)

### 5.3 Matching strategy
Normalize text:
- lowercase
- collapse whitespace
- optionally remove diacritics

Use both:
- `txn_type_code`
- `description_raw`
- `to_account`, `from_account` (when present)

### 5.4 Priority order (to avoid overlaps)
Apply in this order:
1) Paid dividends  
2) Expenses towards government (taxes)  
3) Expenses for employees  
4) Expenses for Car Leasing  
5) Expeses for accountant  
6) Revenue  
7) Other expenses  

### 5.5 Rules (tailored to the sample structure)

#### Paid dividends
Match if outflow AND any of:
- contains `dividende` / `dividend`
- contains `plata dividende` / `profit share`

#### Expenses towards government (taxes)
Match if outflow AND any of:
- contains `trezoreria` (Romanian treasury)
- contains `anaf`
- contains `impozit`
- contains `contributii`
- contains `cam`, `cass`, `cas` (as tokens/words, be careful with false positives)
- contains `tax`

#### Expenses for employees
Match if outflow AND any of:
- contains `salariu`
- contains `payroll`
- contains `cim` (as word boundary)
- contains `wage`, `salary`, `bonus`

#### Expenses for Car Leasing
Match if outflow AND any of:
- contains `leasing`
- contains known lessor keywords:
  - `bcr leasing` (configurable list of counterparties)

#### Expeses for accountant
Match if outflow AND any of:
- contains `contabil`
- contains `contabilitate`
- contains `accounting`
- contains `expert`
- contains known accountant vendor list (configurable), e.g. `optimar consult expert` (from sample)

#### Revenue
Match if inflow AND any of:
- `txn_type_code` in `{MOA, MOR}` OR
- contains `money added` OR `payment received` OR Romanian inflow terms (`incasare`, `incasat`, etc.)

Fallback:
- inflow not matched elsewhere -> Revenue with lower confidence or mark review (configurable).

#### Other expenses
- outflow not matching above rules -> Other expenses
- neutral rows -> Other expenses + review

### 5.6 Confidence + review
Confidence scoring (deterministic):
- Strong match (keyword + correct direction): 0.90
- Vendor-list match: 0.95
- Weak match (partial keyword): 0.70
- Fallback category: 0.40

Set:
- `needs_review = confidence < 0.60`

### 5.7 Manual overrides
Provide ability to override category in UI:
- Store `category_override` and `override_reason`
- Metrics must use override if present.

## 6) Metrics requirements (monthly + drilldowns)

### 6.1 Base definitions
Compute metrics per:
- month (`YYYY-MM`)
- currency (separately by default)
- optionally “all currencies” view (requires FX normalization — out of scope unless explicitly requested)

### 6.2 Exclusions
By default, exclude:
- `is_internal_transfer=true` (EXI/EXO FX movements)

### 6.3 Required monthly metrics
For each month + currency:
- `revenue_total`
- `taxes_total`
- `accountant_total`
- `car_leasing_total`
- `employees_total`
- `dividends_total`
- `other_expenses_total`

Computed:
- `total_expenses_operational = taxes + accountant + car_leasing + employees + other_expenses`
- `net_income_operational = revenue_total - total_expenses_operational`
- `net_cash_after_dividends = revenue_total - (total_expenses_operational + dividends_total)`

Also provide:
- counts of transactions per category
- count of `needs_review=true`

### 6.4 Drilldown views
API must allow querying:
- transactions for a given month/category
- top counterparties in “Other expenses”
- list of transactions needing review

## 7) Backend API requirements (FastAPI)

### 7.1 Endpoints (minimum)

#### Ingestion
- `POST /api/statements/upload`
  - multipart file upload (one PDF)
  - returns `statement_id`, parse summary

- `POST /api/statements/reparse/{statement_id}`
  - re-run parsing + categorization (useful after rule updates)

#### Data access
- `GET /api/transactions`
  - filters: `month`, `currency`, `category`, `needs_review`, `statement_id`
  - pagination + sorting

- `PATCH /api/transactions/{id}`
  - allow setting `category_override`, `override_reason`

#### Metrics
- `GET /api/metrics/monthly`
  - params: `from=YYYY-MM`, `to=YYYY-MM`, `currency=...|all`, `include_internal_transfers=bool`
  - returns time series per category + net income lines

- `GET /api/metrics/summary`
  - totals across a range

### 7.2 Idempotency
If the same PDF is uploaded again:
- detect via SHA256 hash
- do not duplicate records; return existing `statement_id`

### 7.3 Error handling
- If parsing fails for a statement:
  - set `parse_status=fail`
  - store error details and return meaningful message
- If only some transactions parse:
  - `parse_status=partial`
  - include counts + problematic chunks

## 8) Frontend UI requirements (React dashboard)

### 8.1 Core pages

#### Dashboard (Monthly)
- Controls:
  - date range picker (month granularity)
  - currency selector
  - toggle “include internal transfers”
  - toggle “use overrides”
- Charts:
  1) Line chart: `net_income_operational` over time
  2) Stacked bar chart: expenses by category per month
  3) Bar/line: revenue vs expenses per month
- Summary cards:
  - revenue, total expenses, net income, dividends, needs-review count

#### Transactions table (Drilldown)
- Filters: month, category, needs_review, search by description
- Columns: date, type code, description, amount (signed), category, confidence, override indicator
- Row click -> details drawer showing parsed fields and rule reason
- Override UI:
  - dropdown of categories
  - text input for override reason
  - save

#### Rules / Vendors (optional but recommended)
- UI to edit keyword lists and vendor mappings (or maintain as server-side config file)
- “Re-parse all” button

### 8.2 Chart library
- Use **Recharts** (simple + fast) or **Plotly** (richer). Recharts is sufficient.

### 8.3 UX requirements
- Responsive layout (desktop-first ok)
- Export:
  - “Download CSV” for filtered transactions
  - “Download JSON” for monthly metrics

## 9) Configuration requirements

All categorization rules must be externalized (not hardcoded):
- `config/categories.yml`:
  - keywords per category (English + Romanian)
  - vendor mappings (exact and fuzzy)
  - priority order
  - confidence thresholds

## 10) Testing requirements

### 10.1 Unit tests
- Date parsing (e.g., `27 Jan 2026`)
- Amount parsing (spaces as thousands separators; currency symbol `£`; “RON” suffix)
- Transaction chunk segmentation
- ID extraction (`ID: ...`)
- Categorization precedence (dividends vs taxes, etc.)
- EXI/EXO flagged as internal transfer

### 10.2 Integration tests
- Run parser on sample PDF and assert:
  - correct number of transactions extracted per currency block
  - at least these recognitions work (based on sample patterns):
    - Trezoreria -> taxes
    - BCR LEASING -> car leasing
    - “Salariu CIM” -> employees
    - “Plata dividende” -> dividends
    - EXI/EXO -> internal transfer excluded from operational metrics

### 10.3 Golden files
Maintain a small set of labeled statements with expected outputs:
- `expected_transactions.csv`
- `expected_monthly_metrics.json`

## 11) Implementation notes (engineering constraints)

- Use `Decimal` for money.
- Store all money in original currency (no FX conversion unless added later).
- Parsing must be robust to multi-page transaction sections.
- Keep `category_reason` short and explainable, e.g.:
  - `matched_keyword: "trezoreria" (taxes)`
  - `matched_vendor: "bcr leasing" (car leasing)`
  - `txn_type_code=EXI -> internal_transfer`

---

## 12) Deliverables checklist

- [ ] `parser/` module that extracts statement metadata, account blocks, and transactions
- [ ] `categorizer/` module with rule engine + config
- [ ] `metrics/` module computing monthly aggregates
- [ ] FastAPI service + DB migrations
- [ ] React dashboard (charts + drilldowns + overrides)
- [ ] Tests (unit + integration + golden files)
- [ ] README with local dev instructions (backend + frontend)
