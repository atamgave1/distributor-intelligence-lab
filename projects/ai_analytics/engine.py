"""Governed, deterministic analytics demonstration. No live LLM or arbitrary SQL."""
from __future__ import annotations

import calendar
from contextlib import closing
import re
import sqlite3
from pathlib import Path
from urllib.parse import quote

MODE = "rules-based demo, not a live LLM"
AS_OF = "2025-12-31"
BLOCKED = re.compile(r"(?:;|--|/\*|\b(?:drop|delete|update|insert|alter|attach|pragma|select|union|execute)\b|ignore\s+(?:all\s+)?(?:previous|prior)|system\s+prompt)", re.I)
VOCABULARY = set("""a an the show me give get what which have has is are was were our my business distributor
    annual yearly full year for in of by with and total overall all report reporting latest
    revenue revenues sales net gross profit profits margin margins performance summary kpi kpis
    monthly month trend trends category categories product products sku skus customer customers
    client clients top largest concentration region regions regional geography geographical
    receivable receivables aging ageing overdue unpaid working capital cash tied up invoice invoices
    account accounts who owes debtor debtors inventory stock stocks low reorder point points
    forecast forecasting seasonal naive holdout prediction baseline evaluate evaluation backtest
    compare comparison results 2024 2025""".split())


def _result(status, title, explanation, *, columns=None, rows=None, metrics=None, source=None):
    return {
        "status": status, "title": title, "explanation": explanation,
        "columns": columns or [], "rows": rows or [], "metrics": metrics or {},
        "mode": MODE,
        "provenance": {"dataset": "fictional distributor; synthetic data", "as_of": AS_OF,
                       "source": source or [], "currency": "USD", "money_units": "integer cents",
                       "limitations": "Read-only, allowlisted analyses; no live LLM or causal inference."},
    }


def _connect(db_path):
    uri = "file:" + quote(str(Path(db_path).resolve()), safe="/") + "?mode=ro"
    db = sqlite3.connect(uri, uri=True, timeout=3)
    db.execute("PRAGMA query_only=ON")
    # Interrupt expensive queries independently of SQL wording.
    budget = [0]
    def progress():
        budget[0] += 1
        return int(budget[0] > 20000)
    db.set_progress_handler(progress, 1000)
    return db


def _route(q):
    if any(x in q for x in ("forecast", "seasonal naive", "holdout", "prediction baseline")):
        return "forecast"
    if any(x in q for x in ("inventory", "stock", "reorder")):
        return "inventory"
    if any(x in q for x in ("receivable", "aging", "ageing", "overdue", "unpaid", "working capital", "cash tied up", "debtor")):
        if any(x in q for x in ("customer", "account", "who owes", "largest debtor")):
            return "debtors"
        return "aging"
    if any(x in q for x in ("monthly", "month", "trend")):
        return "monthly"
    if any(x in q for x in ("product", "sku")):
        return "product"
    if "categor" in q:
        return "category"
    if any(x in q for x in ("customer", "concentration", "client")):
        return "customer"
    if any(x in q for x in ("region", "geograph")):
        return "region"
    if any(x in q for x in ("revenue", "sales", "profit", "margin", "performance", "summary", "kpi", "business results")):
        return "summary"
    return None


def answer(question: str, db_path: str) -> dict:
    """Answer supported questions with fixed SQL; user input is never SQL."""
    if not isinstance(question, str) or not question.strip():
        return _result("clarify", "Choose an analysis", "Ask about revenue, gross margin, customers, inventory, receivables, or the forecasting baseline.")
    if len(question) > 1500 or BLOCKED.search(question):
        return _result("unsupported", "Request outside the governed interface", "SQL statements and instruction overrides are not accepted. Ask a business question from the supported examples.")
    q = question.lower().strip()
    if any(x in q for x in ("net profit", "ebitda", "churn", "caused", "why did", "why has", "employee", "personal email")):
        return _result("unsupported", "Insufficient data", "This dataset supports gross profit, not operating expenses, causal explanations, employee information, or churn.")
    years = set(re.findall(r"\b20\d{2}\b", q))
    if years - {"2024", "2025"}:
        return _result("unsupported", "Date outside the demonstration", "The synthetic dataset covers 2024–2025. No future forecast is available in this demo.")
    if len(years) > 1 and not any(x in q for x in ("forecast", "holdout", "seasonal naive")):
        return _result("clarify", "Choose one reporting year", "Ask for 2024 or 2025. Year-over-year comparisons are not supported by this interface.")
    # Avoid silently ignoring unsupported filters or time granularity.
    if any(x in q for x in ("quarter", "weekly", "daily", "last week", "last month", "today", "yesterday", "next year", "next month", "only ", "where ", "exclude ", "excluding ")):
        return _result("clarify", "Unsupported filter or time window", "This interface supports full-year sales summaries and groups, plus an as-of inventory/receivables snapshot. Ask without extra filters.")
    if any(name.lower() in q for name in calendar.month_name[1:]):
        return _result("clarify", "Choose a full reporting year", "Month-specific filters are not supported. Ask for a monthly trend for 2024 or 2025.")
    route = _route(q)
    if route is None:
        return _result("unsupported", "Question outside supported analyses", "Try: 2025 revenue summary; monthly revenue; gross margin by category; top customers; revenue by region; receivables aging; overdue customers; low inventory; forecasting baseline.")
    tokens = set(re.findall(r"[a-z0-9]+", q))
    if tokens - VOCABULARY:
        return _result("clarify", "Question includes unsupported terms or filters", "Use one of the documented questions. Named customer/region filters, arbitrary instructions, and extra calculations are not supported; they will not be silently ignored.")
    if re.search(r"\bgross\s+(?:sales|revenue)\b", q):
        return _result("unsupported", "Gross sales are not implemented", "Sales analyses report net revenue after signed returns. Gross sales or gross revenue before returns requires a separate definition and is not substituted with net revenue.")
    if route == "forecast" and re.search(r"\b(?:gross|profit|profits|margin|margins|category|categories|product|products|sku|skus|customer|customers|client|clients|region|regions|regional|geography|geographical|inventory|stock|stocks|reorder|receivable|receivables|aging|ageing|overdue|unpaid|debtor|debtors|capital)\b", q):
        return _result("clarify", "Only aggregate net-revenue forecasting is implemented", "The baseline backtests monthly total net revenue. It cannot forecast profit, margin, inventory, receivables, or grouped category/customer/product/region results. Ask 'forecast baseline'.")
    if route in ("customer", "product", "category", "region") and re.search(r"\b(?:profit|profits|margin|margins)\b", q) and (re.search(r"\b(?:top|largest)\b", q) or re.search(r"\bby\s+(?:gross\s+)?(?:profit|profits|margin|margins)\b", q)):
        return _result("clarify", "Profit and margin rankings are not implemented", "Grouped tables include gross profit and gross margin but are ordered by net revenue. Ask for a breakdown without requesting a profit/margin ranking, or ask for top customers by revenue.")
    snapshot_domains = sum((bool(re.search(r"\b(?:inventory|stock|reorder)\b", q)), bool(re.search(r"\b(?:receivables?|aging|ageing|overdue|unpaid|debtor|working capital)\b", q))))
    if snapshot_domains > 1 or (snapshot_domains and re.search(r"\b(?:revenue|sales|profit|margin|monthly)\b", q)):
        return _result("clarify", "Choose one analysis", "Ask about sales, inventory, or receivables separately.")
    grouping_requests = sum(bool(re.search(pattern, q)) for pattern in (
        r"\b(?:monthly|month|trend|trends)\b", r"\b(?:product|products|sku|skus)\b",
        r"\b(?:category|categories)\b", r"\b(?:customer|customers|client|clients|concentration)\b",
        r"\b(?:region|regions|regional|geography|geographical)\b"))
    if not snapshot_domains and grouping_requests > 1:
        return _result("clarify", "Choose one grouping", "Ask for a monthly, product, category, customer, or region breakdown separately.")
    if route == "forecast" and years == {"2024"}:
        return _result("clarify", "Fixed forecast evaluation period", "This baseline trains on 2024 and evaluates 2025. Ask for the forecast baseline without a different holdout period.")
    if "low" in tokens and route != "inventory":
        return _result("clarify", "Unsupported ranking", "Low-value rankings are not implemented. Sales groups are ordered by revenue; inventory supports low stock.")
    year = next(iter(years), "2025")
    if route in ("aging", "debtors", "inventory") and years == {"2024"}:
        return _result("unsupported", "Historical snapshot unavailable", "Inventory and receivables are a snapshot as of 2025-12-31; a 2024 snapshot is not available.")
    try:
        with closing(_connect(db_path)) as db:
            if route == "forecast":
                return _forecast(db)
            if route == "aging":
                only_overdue = "overdue" in tokens or bool(tokens & {"debtor", "debtors"})
                overdue_filter = " AND days_overdue > 0" if only_overdue else ""
                rows = db.execute(f"""SELECT CASE WHEN days_overdue <= 0 THEN 'Current'
                    WHEN days_overdue <= 30 THEN '1–30 days' WHEN days_overdue <= 60 THEN '31–60 days'
                    WHEN days_overdue <= 90 THEN '61–90 days' ELSE '90+ days' END AS bucket,
                    COUNT(*), SUM(outstanding_cents) FROM v_receivables WHERE outstanding_cents > 0 {overdue_filter}
                    GROUP BY bucket ORDER BY MIN(days_overdue)"""
                ).fetchall()
                title = "Overdue receivables aging" if only_overdue else "Receivables aging"
                scope = "Only overdue invoices are included; current invoices are excluded." if only_overdue else "All open invoices are included, including current invoices."
                return _result("ok", title, f"Open invoice balances after credits and payments, aged as of 2025-12-31. Overdue means days_overdue > 0. {scope}",
                    columns=["aging_bucket", "open_invoices", "outstanding_cents"], rows=[list(r) for r in rows],
                    metrics={"total_outstanding_cents": sum(r[2] for r in rows)}, source=["v_receivables"])
            if route == "debtors":
                only_overdue = "overdue" in tokens or bool(tokens & {"debtor", "debtors"})
                overdue_filter = " AND days_overdue > 0" if only_overdue else ""
                rows = db.execute(f"""SELECT customer_id, customer_name, SUM(outstanding_cents), COUNT(*)
                    FROM v_receivables WHERE outstanding_cents > 0 {overdue_filter}
                    GROUP BY customer_id, customer_name ORDER BY SUM(outstanding_cents) DESC, customer_id LIMIT 20"""
                ).fetchall()
                title = "Customers with overdue receivables" if only_overdue else "Customers with open receivables"
                note = "Top 20 customers by overdue outstanding cents; current invoices are excluded." if only_overdue else "Top 20 customers by all open outstanding cents; current and overdue invoices are both included."
                return _result("ok", title, note + " This is credit exposure, not a prediction of default.",
                    columns=["customer_id", "customer_name", "overdue_cents" if only_overdue else "outstanding_cents", "overdue_invoices" if only_overdue else "open_invoices"], rows=[list(r) for r in rows], source=["v_receivables"])
            if route == "inventory":
                rows = db.execute("""SELECT i.product_id, p.name, i.on_hand_units, i.reorder_point,
                    i.on_hand_units * p.unit_cost_cents AS inventory_cost_cents
                    FROM inventory i JOIN products p ON p.product_id = i.product_id
                    WHERE i.snapshot_date = ? AND i.on_hand_units <= i.reorder_point
                    ORDER BY i.on_hand_units - i.reorder_point, i.product_id LIMIT 30""", (AS_OF,)).fetchall()
                return _result("ok", "Inventory at or below reorder point", "As-of stock exceptions, including equality with the reorder point. Inventory value uses unit cost. Reorder points are supplied synthetic inputs, not optimized recommendations.",
                    columns=["product_id", "product_name", "on_hand_units", "reorder_point", "inventory_cost_cents"], rows=[list(r) for r in rows], source=["inventory", "products"])
            bounds = (year + "-01-01", str(int(year) + 1) + "-01-01")
            total = db.execute("""SELECT COALESCE(SUM(net_revenue_cents),0), COALESCE(SUM(cogs_cents),0)
                FROM v_sales WHERE event_date >= ? AND event_date < ?""", bounds).fetchone()
            revenue, cogs = total
            metrics = {"reporting_year": year, "net_revenue_cents": revenue, "cogs_cents": cogs,
                       "gross_profit_cents": revenue - cogs,
                       "gross_margin_percent": round(100 * (revenue - cogs) / revenue, 4) if revenue else None}
            note = f"Reporting year {year}; default is 2025. Net revenue and COGS include signed return events. Gross profit = net revenue − COGS; margin = gross profit / net revenue. No operating expenses are included."
            if route == "summary":
                return _result("ok", f"{year} revenue and gross margin", note, metrics=metrics, source=["v_sales"])
            # SQL fragments are compile-time constants selected by an internal allowlist.
            groups = {"monthly": ("substr(event_date, 1, 7)", "month"), "category": ("category", "category"),
                      "region": ("region", "region"), "product": ("product_id, product_name", "product"),
                      "customer": ("customer_id, customer_name", "customer")}
            group, label = groups[route]
            order = "1" if route == "monthly" else "SUM(net_revenue_cents) DESC, 1"
            rows = db.execute(f"SELECT {group}, SUM(net_revenue_cents), SUM(cogs_cents) FROM v_sales WHERE event_date >= ? AND event_date < ? GROUP BY {group} ORDER BY {order} LIMIT 100", bounds).fetchall()
            identifiers = ["product_id", "product_name"] if route == "product" else ["customer_id", "customer_name"] if route == "customer" else [label]
            out = []
            for row in rows:
                rev, cost = row[-2:]
                out.append(list(row[:-2]) + [rev, cost, rev - cost, round(100 * (rev-cost)/rev, 4) if rev else None])
            if route == "customer":
                metrics["largest_customer_revenue_share_percent"] = round(100 * rows[0][-2]/revenue, 4) if rows and revenue else None
            return _result("ok", f"{year} results by {label}", note + " Groups are ordered by net revenue (months chronologically); at most 100 groups are returned.",
                columns=identifiers + ["net_revenue_cents", "cogs_cents", "gross_profit_cents", "gross_margin_percent"], rows=out, metrics=metrics, source=["v_sales"])
    except (sqlite3.Error, OSError, ValueError):
        return _result("unsupported", "Dataset unavailable", "The required synthetic dataset could not be queried. Generate it and retry; no database changes were made.")


def _forecast(db):
    months = dict(db.execute("""SELECT substr(event_date,1,7), SUM(net_revenue_cents) FROM v_sales
        WHERE event_date >= '2024-01-01' AND event_date < '2026-01-01' GROUP BY 1""").fetchall())
    required = [f"{year}-{month:02d}" for year in (2024, 2025) for month in range(1, 13)]
    if any(m not in months for m in required):
        return _result("unsupported", "Forecast evaluation needs complete history", "Both 2024 and 2025 must have observations in all 12 months; missing months are not silently treated as zero.", source=["v_sales"])
    train = [months[f"2024-{m:02d}"] for m in range(1, 13)]
    actual = [months[f"2025-{m:02d}"] for m in range(1, 13)]
    baseline = round(sum(train)/12)
    seasonal_errors = [abs(a-p) for a,p in zip(actual, train)]
    flat_errors = [abs(a-baseline) for a in actual]
    denom = sum(abs(x) for x in actual)
    rows = [[f"2025-{i+1:02d}", actual[i], train[i], baseline, seasonal_errors[i]] for i in range(12)]
    return _result("ok", "Revenue forecasting baseline: 2025 holdout",
        "Backtest only: train on 2024, predict each 2025 month with the same month of 2024 (seasonal naive), and compare with the fixed 2024 monthly mean. No 2025 observations enter predictions. This is a statistical baseline, not an AI forecast or a future revenue commitment. One year of training limits reliability.",
        columns=["month", "actual_cents", "seasonal_naive_prediction_cents", "training_mean_prediction_cents", "absolute_error_cents"], rows=rows,
        metrics={"training_period": "2024-01 through 2024-12", "holdout_period": "2025-01 through 2025-12", "holdout_months": 12,
                 "seasonal_naive_mae_cents": round(sum(seasonal_errors)/12, 4),
                 "training_mean_mae_cents": round(sum(flat_errors)/12, 4),
                 "seasonal_naive_wape_percent": round(100*sum(seasonal_errors)/denom, 4) if denom else None,
                 "training_mean_wape_percent": round(100*sum(flat_errors)/denom, 4) if denom else None}, source=["v_sales"])
