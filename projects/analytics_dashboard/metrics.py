"""Read-only metrics for the synthetic distributor's local dashboard."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

AS_OF = "2025-12-31"


def dashboard(db_path: str) -> dict:
    """Return integer-cent measures and a dimension cube for client-side filters.

    Sales filters apply to event dates. Receivables and inventory are snapshots,
    deliberately not filtered by the dashboard's sales year. No SQL is supplied
    by the browser. The connection cannot write to the database.
    """
    path = Path(db_path).resolve()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as con:
        con.row_factory = sqlite3.Row
        sales = [dict(row) for row in con.execute("""
            SELECT substr(event_date,1,7) AS month, customer_id, customer_name,
                   segment, region, category,
                   SUM(net_revenue_cents) AS revenue_cents,
                   SUM(cogs_cents) AS cogs_cents,
                   SUM(net_revenue_cents-cogs_cents) AS gross_profit_cents,
                   SUM(CASE WHEN net_revenue_cents>0 THEN net_revenue_cents ELSE 0 END) AS gross_sales_cents,
                   -SUM(CASE WHEN net_revenue_cents<0 THEN net_revenue_cents ELSE 0 END) AS return_credits_cents,
                   SUM(units) AS units
            FROM v_sales WHERE event_date<=?
            GROUP BY substr(event_date,1,7), customer_id, customer_name,
                     segment, region, category
            ORDER BY month, customer_name, category
        """, (AS_OF,))]
        receivables = [dict(row) for row in con.execute("""
            SELECT invoice_id, customer_id, customer_name, segment, region,
                   invoice_date, due_date, invoice_amount_cents, credit_cents,
                   paid_cents, outstanding_cents, days_overdue
            FROM v_receivables WHERE invoice_date<=? AND outstanding_cents>0
            ORDER BY days_overdue DESC, outstanding_cents DESC, invoice_id
        """, (AS_OF,))]
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        inventory = []
        if {"inventory", "products"} <= tables:
            inventory = [dict(row) for row in con.execute("""
                SELECT i.snapshot_date, p.product_id, p.sku, p.name AS product_name,
                       p.category, i.on_hand_units, i.reorder_point,
                       p.unit_cost_cents, i.on_hand_units*p.unit_cost_cents AS stock_value_cents
                FROM inventory i JOIN products p USING (product_id)
                WHERE i.snapshot_date=(SELECT MAX(snapshot_date) FROM inventory WHERE snapshot_date<=?)
                ORDER BY stock_value_cents DESC, p.product_id
            """, (AS_OF,))]

    totals = {key: sum(r[key] or 0 for r in sales) for key in
              ("revenue_cents", "gross_profit_cents", "gross_sales_cents", "return_credits_cents")}
    totals["gross_margin_percent"] = _percent(totals["gross_profit_cents"], totals["revenue_cents"])
    totals["return_credit_percent"] = _percent(totals["return_credits_cents"], totals["gross_sales_cents"])
    totals["receivables_cents"] = sum(r["outstanding_cents"] for r in receivables)
    totals["overdue_cents"] = sum(r["outstanding_cents"] for r in receivables if r["days_overdue"] > 0)
    totals["inventory_cost_cents"] = sum(r["stock_value_cents"] for r in inventory)
    monthly = _group(sales, "month")
    return {
        "metadata": {"title": "Northstar Distribution", "as_of": AS_OF,
                     "currency": "USD", "synthetic": True,
                     "deployment": "Local prototype; AWS deployment pending"},
        "filters": {"years": sorted({r["month"][:4] for r in sales}),
                    "segments": sorted({r["segment"] for r in sales}),
                    "regions": sorted({r["region"] for r in sales}),
                    "categories": sorted({r["category"] for r in sales})},
        "summary": totals, "monthly": monthly,
        "categories": _group(sales, "category"),
        "customers": _group(sales, "customer_name"),
        "sales": sales, "receivables": receivables, "inventory": inventory,
        "aging": _aging(receivables),
        "definitions": {
            "net_revenue": "Signed sales less return credits; excludes tax. Returns are recognized on their event date.",
            "gross_profit": "Net revenue less signed cost of goods sold. Return events reverse the associated cost.",
            "gross_margin": "Total gross profit / total net revenue. No average of row percentages. Undefined at zero revenue.",
            "return_credit_rate": "Absolute negative revenue / positive sales revenue. This is a value-based credit rate, not a unit return rate.",
            "receivables": "Open invoice balances as of 2025-12-31 after credit notes and allocated payments; positive balances only.",
            "overdue": "Open balances with days_overdue > 0; invoices due today are current.",
            "inventory": "Latest available snapshot on or before 2025-12-31, valued at product unit cost. Low stock means on-hand units at or below reorder point.",
            "filter_scope": "Year and category filter sales; region and segment filter sales and receivables. Category filters inventory. Year does not change snapshot dates."
        }
    }


def _percent(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 4) if denominator else None


def _group(rows: list[dict], dimension: str) -> list[dict]:
    result = {}
    for row in rows:
        key = row[dimension]
        target = result.setdefault(key, {dimension: key, "revenue_cents": 0, "gross_profit_cents": 0,
                                         "gross_sales_cents": 0, "return_credits_cents": 0})
        for field in ("revenue_cents", "gross_profit_cents", "gross_sales_cents", "return_credits_cents"):
            target[field] += row[field] or 0
    return [result[key] for key in sorted(result)]


def _aging(rows: list[dict]) -> list[dict]:
    totals = {name: 0 for name in ("Current", "1–30 days", "31–60 days", "61–90 days", "90+ days")}
    for row in rows:
        days = row["days_overdue"]
        bucket = "Current" if days <= 0 else "1–30 days" if days <= 30 else "31–60 days" if days <= 60 else "61–90 days" if days <= 90 else "90+ days"
        totals[bucket] += row["outstanding_cents"]
    return [{"bucket": key, "outstanding_cents": value} for key, value in totals.items()]
