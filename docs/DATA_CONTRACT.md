# Synthetic data and metric contract — v1.0.0

Generator: `portfolio_shared/data.py`; seed: 41729; reporting cutoff: **2025-12-31**. Currency: USD; monetary storage: integer cents; dates: calendar dates without intraday timezone semantics. The dataset is fictional and does not reproduce any particular business.

## Tables

| Table | Grain / meaning |
|---|---|
| customers | One fictional customer; segment and region are static attributes |
| products | One fictional SKU; catalog cost and list price are reference values |
| orders | One invoiced order |
| order_lines | One product line, including transaction price, cost, discount, and rounded line amount |
| returns | One partial line return, refund, and cost reversal |
| invoices | One invoice per order, with invoice and due dates |
| payments | One simulated payment allocation per invoice where payment exists |
| inventory | One end-of-month product snapshot; history covers 2025 |
| sales_ledger | One positive sales event or negative return event |

`v_sales` enriches the ledger with customer / product attributes without multiplying its grain. `v_receivables` aggregates invoice lines, credits and payments independently before joining. The latter is a fixed as-of snapshot, not an arbitrary historical receivables reconstruction.

## Metric definitions

- **Net revenue:** sum of `net_revenue_cents`; excludes tax, includes line discounts and negative posted returns. A return is recognized on its return date, which may differ from the original sale year.
- **Cost of goods sold:** transaction cost times quantity, reversed for returned units. Product catalog cost can differ from historical transaction cost.
- **Gross profit:** net revenue minus cost of goods sold. This excludes payroll, freight, overhead, tax and financing costs; it is not EBITDA or net profit.
- **Gross margin %:** total gross profit divided by total net revenue times 100. Do not average line percentages. A zero revenue denominator returns no ratio.
- **Invoice balance:** invoiced line amounts minus posted credit notes minus allocated payments, as of the reporting cutoff.
- **Overdue:** a positive balance with a due date strictly before the cutoff. An invoice due on the cutoff is current.
- **Aging:** mutually exclusive current, 1–30, 31–60, 61–90, and 91+ days overdue buckets, subject to dashboard implementation labels.
- **Inventory value:** on-hand units at the selected snapshot multiplied by catalog unit cost. Reorder points are fictional policy thresholds, not demand forecasts.

The generator deliberately adds a 2025 second-half Electrical cost / discount squeeze, some partly unpaid invoices, and elevated stock for selected items. These are scenario fixtures, not discoveries from a real client.

## Verification strategy

The generator accumulates expected totals in Python while constructing records. Tests compare those references with independently aggregated SQL views, check cross-year return recognition, foreign keys, return limits, read-only enforcement, and reproducibility. Component tests add explicit tiny fixtures and failure scenarios. Generated reference totals are not a substitute for external accounting validation.

## Sharing

CSV exports are accompanied by SHA-256 checksums. Export metadata is excluded from source-table files. Identifiers and names use `Demo` / `DEMO` prefixes. Never combine these records with client exports without revisiting publication scope.
