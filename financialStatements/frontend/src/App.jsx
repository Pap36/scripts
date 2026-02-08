import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import {
  fetchMetricsMonthly,
  fetchMetricsSummary,
  fetchStatements,
  fetchTransactions,
  updateStatement,
  updateTransaction,
  uploadStatement
} from "./api";

const CATEGORIES = [
  "Revenue",
  "Expenses towards government (taxes)",
  "Expeses for accountant",
  "Expenses for Car Leasing",
  "Leasing Fuel Expenses",
  "Expenses for employees",
  "Paid dividends",
  "Internal transfer",
  "Other expenses"
];

const monthString = (value) => {
  const date = new Date(value);
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  return `${date.getFullYear()}-${month}`;
};

const defaultRange = () => {
  const now = new Date();
  const toMonth = monthString(now);
  const from = new Date(now.getFullYear(), now.getMonth() - 5, 1);
  return { fromMonth: monthString(from), toMonth };
};

const formatMoney = (value, currencyCode) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  const formatted = Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
  return currencyCode ? `${formatted} ${currencyCode}` : formatted;
};

// Formatter for chart axis (shorter, no currency)
const formatAxisValue = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  });
};

// Formatter for chart tooltips (with 2 decimals)
const formatTooltipValue = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
};

const applySign = (value, direction) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return null;
  }
  const numeric = Number(value);
  if (direction === "outflow") return -Math.abs(numeric);
  if (direction === "inflow") return Math.abs(numeric);
  return numeric;
};

const isValidMonth = (value) => /^\d{4}-\d{2}$/.test(value);

const EXPENSE_COLORS = {
  Taxes: "#ef4444",
  Accountant: "#f97316",
  "Car leasing": "#facc15",
  "Leasing fuel": "#06b6d4",
  Employees: "#22c55e",
  Dividends: "#8b5cf6",
  Transfers: "#ec4899",
  Other: "#6366f1"
};

export default function App() {
  const [{ fromMonth, toMonth }, setRange] = useState(defaultRange);
  const [currency, setCurrency] = useState("all");
  const [useOverrides, setUseOverrides] = useState(true);
  const [includeTransfers, setIncludeTransfers] = useState(false);
  const [metrics, setMetrics] = useState([]);
  const [summary, setSummary] = useState({});
  const [transactions, setTransactions] = useState([]);
  const [statements, setStatements] = useState([]);
  const [txnTotal, setTxnTotal] = useState(0);
  const [txnPage, setTxnPage] = useState(1);
  const [txnCategory, setTxnCategory] = useState("");
  const [txnMonth, setTxnMonth] = useState("");
  const [needsReview, setNeedsReview] = useState(false);
  const [loading, setLoading] = useState(false);

  const refreshMetrics = async () => {
    if (!isValidMonth(fromMonth) || !isValidMonth(toMonth)) {
      return;
    }
    const params = {
      from_month: fromMonth,
      to_month: toMonth,
      currency,
      use_overrides: useOverrides
    };
    const [metricItems, totals] = await Promise.all([
      fetchMetricsMonthly(params),
      fetchMetricsSummary(params)
    ]);
    setMetrics(metricItems);
    setSummary(totals);
  };

  useEffect(() => {
    const load = async () => {
      if (!isValidMonth(fromMonth) || !isValidMonth(toMonth)) {
        setLoading(false);
        return;
      }
      setLoading(true);
      await refreshMetrics();
      setLoading(false);
    };
    load();
  }, [fromMonth, toMonth, currency, useOverrides]);

  useEffect(() => {
    const loadStatements = async () => {
      const items = await fetchStatements();
      setStatements(items);
    };
    loadStatements();
  }, []);

  useEffect(() => {
    const loadTransactions = async () => {
      const params = {
        page: txnPage,
        page_size: 20
      };
      if (txnCategory) params.category = txnCategory;
      if (txnMonth) params.month = txnMonth;
      if (needsReview) params.needs_review = true;
      if (currency !== "all") params.currency = currency;

      const data = await fetchTransactions(params);
      setTransactions(data.items);
      setTxnTotal(data.total);
    };
    loadTransactions();
  }, [txnPage, txnCategory, txnMonth, needsReview, currency]);

  const expenseStackData = useMemo(() => {
    return metrics.map((item) => {
      const base = {
        month: item.month,
        taxes: item.taxes_total,
        accountant: item.accountant_total,
        carLeasing: item.car_leasing_total,
        leasingFuel: item.leasing_fuel_total,
        employees: item.employees_total,
        dividends: item.dividends_total,
        other: item.other_expenses_total
      };
      if (includeTransfers) {
        base.transfers = item.transfers_out_ron || item.transfers_out || 0;
      }
      return base;
    });
  }, [metrics, includeTransfers]);


  const revenueExpenseData = useMemo(() => {
    return metrics.map((item) => {
      const transfersOut = item.transfers_out_ron || item.transfers_out || 0;
      const transfersIn = item.transfers_in_ron || item.transfers_in || 0;
      return {
        month: item.month,
        revenue: includeTransfers ? item.revenue_total + transfersIn : item.revenue_total,
        expenses: includeTransfers ? item.total_expenses_operational + transfersOut : item.total_expenses_operational
      };
    });
  }, [metrics, includeTransfers]);


  const cumulativeNetIncomeData = useMemo(() => {
    let runningTotal = 0;
    return metrics.map((item) => {
      runningTotal += item.net_income_operational || 0;
      return {
        ...item,
        net_income_cumulative: runningTotal
      };
    });
  }, [metrics]);



  const expenseTotalsData = useMemo(() => {
    const data = [
      { name: "Taxes", value: summary.taxes_total || 0 },
      { name: "Accountant", value: summary.accountant_total || 0 },
      { name: "Car leasing", value: summary.car_leasing_total || 0 },
      { name: "Leasing fuel", value: summary.leasing_fuel_total || 0 },
      { name: "Employees", value: summary.employees_total || 0 },
      { name: "Dividends", value: summary.dividends_total || 0 },
      { name: "Other", value: summary.other_expenses_total || 0 }
    ];
    if (includeTransfers) {
      data.push({ name: "Transfers", value: summary.transfers_out_ron || summary.transfers_out || 0 });
    }
    return data;
  }, [summary, includeTransfers]);

  const refreshTransactions = async () => {
    const data = await fetchTransactions({
      page: txnPage,
      page_size: 20,
      category: txnCategory || undefined,
      month: txnMonth || undefined,
      needs_review: needsReview || undefined,
      currency: currency !== "all" ? currency : undefined
    });
    setTransactions(data.items);
    setTxnTotal(data.total);
  };

  const refreshStatements = async () => {
    const items = await fetchStatements();
    setStatements(items);
  };

  const handleUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await uploadStatement(file);
    await refreshStatements();
  };

  const handleStatementToggle = async (statementId, nextValue) => {
    await updateStatement(statementId, { include_in_metrics: nextValue });
    await Promise.all([refreshStatements(), refreshMetrics(), refreshTransactions()]);
  };

  const handleOverride = async (txn, categoryOverride) => {
    await updateTransaction(txn.id, {
      category_override: categoryOverride,
      amount_override: txn.amount_override ?? null,
      override_reason: "Manual override from dashboard"
    });
    await refreshTransactions();
  };

  const handleAmountOverride = async (txn, value) => {
    const amountValue = value === "" ? null : Number(value);
    await updateTransaction(txn.id, {
      amount_override: Number.isNaN(amountValue) ? null : amountValue,
      category_override: txn.category_override ?? null,
      override_reason: "Manual amount override"
    });
    await refreshTransactions();
  };

  const handleSignOverride = async (txn, checked) => {
    await updateTransaction(txn.id, {
      sign_override: checked || null,
      amount_override: txn.amount_override ?? null,
      category_override: txn.category_override ?? null,
      override_reason: "Sign override"
    });
    await refreshTransactions();
  };

  const summaryCurrency = currency === "all" ? "RON" : currency;

  return (
    <div className="app">
      <header className="hero">
        <div>
          <p className="eyebrow">Financial Statements</p>
          <h1>Monthly Performance Dashboard</h1>
          <p className="subtitle">Parse Revolut statements, classify cash flows, and monitor KPIs.</p>
        </div>
        <div className="controls">
          <label>
            From
            <input
              type="month"
              value={fromMonth}
              onChange={(event) =>
                setRange((prev) => ({
                  ...prev,
                  fromMonth: event.target.value
                }))
              }
            />
          </label>
          <label>
            To
            <input
              type="month"
              value={toMonth}
              onChange={(event) =>
                setRange((prev) => ({
                  ...prev,
                  toMonth: event.target.value
                }))
              }
            />
          </label>
          <label>
            Currency
            <select value={currency} onChange={(event) => setCurrency(event.target.value)}>
              <option value="all">All</option>
              <option value="RON">RON</option>
              <option value="GBP">GBP</option>
              <option value="EUR">EUR</option>
            </select>
          </label>
          <label className="toggle">
            <input
              type="checkbox"
              checked={useOverrides}
              onChange={(event) => setUseOverrides(event.target.checked)}
            />
            Use overrides
          </label>
          <label className="toggle">
            <input
              type="checkbox"
              checked={includeTransfers}
              onChange={(event) => setIncludeTransfers(event.target.checked)}
            />
            Include transfers in charts
          </label>
        </div>
      </header>

      <section className="summary">
        <SummaryCard title="Revenue" value={summary.revenue_total} currency={summaryCurrency} />
        <SummaryCard title="Total expenses" value={summary.total_expenses_operational} currency={summaryCurrency} />
        <SummaryCard title="Net income" value={summary.net_income_operational} currency={summaryCurrency} />
        <SummaryCard title="Dividends" value={summary.dividends_total} currency={summaryCurrency} />
        <SummaryCard title="Needs review" value={summary.needs_review_count} isCount />
      </section>

      {currency === "all" && (
        <section className="summary transfers-summary">
          <SummaryCard 
            title="Transfers In (to RON)" 
            value={summary.transfers_in_ron} 
            currency="RON" 
          />
          <SummaryCard 
            title={`Transfers Out (from ${summary.transfers_out_currency || 'GBP'})`}
            value={summary.transfers_out_original} 
            currency={summary.transfers_out_currency || 'GBP'} 
          />
          <SummaryCard 
            title="Avg FX Rate" 
            value={summary.avg_fx_rate ? `${summary.avg_fx_rate.toFixed(4)} RON/${summary.transfers_out_currency || 'GBP'}` : "-"} 
          />
          <SummaryCard 
            title="Revenue - Transfers In" 
            value={(summary.revenue_total || 0) - (summary.transfers_in_ron || 0)} 
            currency="RON" 
          />
          <SummaryCard 
            title="Expenses - Transfers Out (RON)" 
            value={(summary.total_expenses_operational || 0) - (summary.transfers_out_original || 0) * (summary.avg_fx_rate || 0)} 
            currency="RON" 
          />
        </section>
      )}

      <section className="panel">
        <div className="panel-header">
          <h2>Statements</h2>
          <div className="filters">
            <label className="upload">
              Upload PDF
              <input type="file" accept="application/pdf" onChange={handleUpload} />
            </label>
          </div>
        </div>
        <div className="table">
          <div className="table-row header">
            <span>Included</span>
            <span>File</span>
            <span>Imported</span>
            <span>Pages</span>
            <span>Status</span>
          </div>
          {statements.map((statement) => (
            <div className="table-row" key={statement.statement_id}>
              <span>
                <input
                  type="checkbox"
                  checked={statement.include_in_metrics}
                  onChange={(event) =>
                    handleStatementToggle(statement.statement_id, event.target.checked)
                  }
                />
              </span>
              <span className="truncate">{statement.file_name}</span>
              <span>{new Date(statement.imported_at).toLocaleString()}</span>
              <span>{statement.pages}</span>
              <span>{statement.parse_status}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="grid">
        <Panel title="Cumulative net income">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={cumulativeNetIncomeData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis tickFormatter={formatAxisValue} />
              <Tooltip formatter={formatTooltipValue} />
              <Line type="monotone" dataKey="net_income_cumulative" stroke="#2563eb" strokeWidth={3} />
            </LineChart>
          </ResponsiveContainer>
        </Panel>
        <Panel title="Total expenses by category">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={expenseTotalsData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis tickFormatter={formatAxisValue} />
              <Tooltip formatter={formatTooltipValue} />
              <Bar dataKey="value">
                {expenseTotalsData.map((entry) => (
                  <Cell key={entry.name} fill={EXPENSE_COLORS[entry.name] || "#6366f1"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
        <Panel title="Expenses by category">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={expenseStackData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis tickFormatter={formatAxisValue} />
              <Tooltip formatter={formatTooltipValue} />
              <Legend />
              <Bar dataKey="taxes" stackId="a" fill="#ef4444" />
              <Bar dataKey="accountant" stackId="a" fill="#f97316" />
              <Bar dataKey="carLeasing" stackId="a" fill="#facc15" />
              <Bar dataKey="leasingFuel" stackId="a" fill="#06b6d4" />
              <Bar dataKey="employees" stackId="a" fill="#22c55e" />
              <Bar dataKey="dividends" stackId="a" fill="#8b5cf6" />
              <Bar dataKey="other" stackId="a" fill="#6366f1" />
              {includeTransfers && <Bar dataKey="transfers" stackId="a" fill="#ec4899" />}
            </BarChart>
          </ResponsiveContainer>
        </Panel>
        <Panel title="Revenue vs expenses">
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={revenueExpenseData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis tickFormatter={formatAxisValue} />
              <Tooltip formatter={formatTooltipValue} />
              <Legend />
              <Bar dataKey="revenue" fill="#16a34a" />
              <Bar dataKey="expenses" fill="#dc2626" />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Transactions</h2>
          <div className="filters">
            <select value={txnMonth} onChange={(event) => setTxnMonth(event.target.value)}>
              <option value="">All months</option>
              {metrics.map((item) => (
                <option key={item.month} value={item.month}>
                  {item.month}
                </option>
              ))}
            </select>
            <select value={txnCategory} onChange={(event) => setTxnCategory(event.target.value)}>
              <option value="">All categories</option>
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
            <label className="toggle">
              <input
                type="checkbox"
                checked={needsReview}
                onChange={(event) => setNeedsReview(event.target.checked)}
              />
              Needs review
            </label>
          </div>
        </div>
        <div className="table">
          <div className="table-row header">
            <span>Date</span>
            <span>Description</span>
            <span>Amount</span>
            <span>Amount override</span>
            <span>Flip</span>
            <span>Category</span>
            <span>Confidence</span>
            <span>FX Rate</span>
            <span>Override</span>
          </div>
          {transactions.map((txn) => (
            <div className="table-row" key={txn.id}>
              {(() => {
                let effectiveSigned =
                  txn.amount_override !== null && txn.amount_override !== undefined
                    ? applySign(txn.amount_override, txn.direction)
                    : txn.signed_amount;
                if (txn.sign_override) {
                  effectiveSigned = -effectiveSigned;
                }
                return (
                  <>
              <span>{txn.txn_date_utc}</span>
              <span className="truncate">{txn.description_raw}</span>
              <span className={effectiveSigned < 0 ? "negative" : "positive"}>
                {formatMoney(effectiveSigned, txn.account_currency)}
              </span>
              <span>
                <input
                  type="number"
                  step="0.01"
                  defaultValue={txn.amount_override ?? ""}
                  placeholder="Auto"
                  onBlur={(event) => handleAmountOverride(txn, event.target.value)}
                />
              </span>
              <span>
                <input
                  type="checkbox"
                  checked={txn.sign_override || false}
                  onChange={(e) => handleSignOverride(txn, e.target.checked)}
                  title="Flip sign (e.g. refund shown as expense)"
                />
              </span>
              <span>{txn.is_internal_transfer ? "Internal transfer" : txn.category}</span>
              <span>{(txn.confidence * 100).toFixed(0)}%</span>
              <span>
                {txn.fx_rate_applied
                  ? `${Number(txn.fx_rate_applied).toFixed(4)}${txn.fx_rate_official ? ` (BNR ${Number(txn.fx_rate_official).toFixed(4)})` : ""} RON/GBP`
                  : "-"}
              </span>
              <span>
                <select
                  value={txn.category_override || ""}
                  onChange={(event) => handleOverride(txn, event.target.value || null)}
                >
                  <option value="">Auto</option>
                  {CATEGORIES.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </select>
              </span>
                  </>
                );
              })()}
            </div>
          ))}
        </div>
        <div className="pagination">
          <button disabled={txnPage === 1} onClick={() => setTxnPage((p) => Math.max(1, p - 1))}>
            Previous
          </button>
          <span>
            Page {txnPage} of {Math.max(1, Math.ceil(txnTotal / 20))}
          </span>
          <button
            disabled={txnPage >= Math.ceil(txnTotal / 20)}
            onClick={() => setTxnPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      </section>

      {loading && <div className="loading">Loading...</div>}
    </div>
  );
}

function Panel({ title, children }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <h2>{title}</h2>
      </div>
      {children}
    </div>
  );
}

function SummaryCard({ title, value, currency, isCount = false }) {
  // If value is already a string (pre-formatted), use it directly
  const displayValue = typeof value === 'string' 
    ? value 
    : (isCount ? Number(value || 0).toLocaleString() : formatMoney(value || 0, currency));

  return (
    <div className="card">
      <p>{title}</p>
      <h3>{displayValue}</h3>
    </div>
  );
}
