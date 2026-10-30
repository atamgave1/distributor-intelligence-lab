# Governed analytics assistant and forecast baseline

This is a working **rules-based demo, not a live LLM**. It answers a bounded set of business questions against a fictional distributor's synthetic data. It is a portfolio demonstration, not a deployment for a named client or evidence of actual client savings.

## Business use case

A finance or operations leader needs a consistent view of net sales, gross margin, customer concentration, inventory exceptions, and receivables exposure. The assistant provides repeatable answers with definitions and source provenance. A separate forecasting backtest demonstrates a measured statistical baseline without claiming predictive AI capabilities.

The shared dataset covers 2024–2025 sales and a 2025-12-31 receivables/inventory snapshot. Revenue is synthetic and is not a client result. This module needs no network, credentials, packages, or paid service.

## Run

From the `portfolio-lab` repository root:

```sh
python3 -m unittest discover -s projects/ai_analytics -p 'test_*.py' -v
```

Use the parent's shared data generator and UI, or call the interface directly:

```python
from portfolio_shared.data import ensure_database
from projects.ai_analytics.engine import answer

database = ensure_database()
result = answer("2025 revenue summary", str(database))
```

`answer(question: str, db_path: str) -> dict` returns JSON-compatible `status`, `title`, `explanation`, `columns`, `rows`, `metrics`, `mode`, and `provenance`. Status is `ok`, `clarify`, or `unsupported`. Tables contain row arrays aligned to the column-name array. Currency amounts are integer **USD cents**; percentages are numeric percentage points, not fractions. The parent UI must escape every displayed text value, including question and dataset text.

## Supported examples

| Question | Result |
|---|---|
| `2025 revenue summary` | Net revenue, COGS, gross profit, gross margin |
| `2024 sales` | Same definitions for the earlier reporting year |
| `Monthly revenue` | Monthly results for the default year, 2025 |
| `Revenue by category` | Category revenue and margin |
| `Sales by product` | Product revenue and margin |
| `Top customers` | Customer results ranked by revenue and largest-customer share |
| `Revenue by region` | Region results |
| `Receivables aging` | Open balances by aging bucket |
| `Overdue invoices` | Aging of overdue balances only; current invoices excluded |
| `Overdue customers` | Top 20 customers by overdue outstanding balance |
| `Unpaid customer accounts` | Top 20 customers by all open balances, including current invoices |
| `Low inventory` | Up to 30 products at or below their supplied reorder points |
| `Forecast baseline` | Full 2025 holdout evaluation of two 2024-trained baselines |

The language interface uses fixed routing and a constrained vocabulary. It does not understand arbitrary questions. Named-customer filters, named-region filters, multi-dimensional groupings, operating profit, causal questions, arbitrary dates, and arbitrary SQL are rejected or request clarification rather than silently applied. Gross sales/revenue before returns is not implemented and will not be substituted with net revenue. Profit/margin rankings are not implemented; requests such as `top customers by gross profit` ask for clarification. Forecasting is only for aggregate monthly net revenue; profit/margin, inventory, receivables, and category/customer/product/region forecasts are not substituted with an aggregate revenue forecast. Ask one analysis at a time. Sales groupings return at most 100 groups, ordered by revenue or chronologically for months. Full-year summary metrics use all qualifying rows, not only the displayed groups. Explicit future years are unsupported. Missing sales months are absent from grouped output, not imputed.

## Metric definitions

- **Net revenue:** signed `net_revenue_cents`, including return events, restricted by event date to the reporting year.
- **COGS:** signed `cogs_cents` over the same events. A negative return reverses the corresponding cost.
- **Gross profit:** net revenue minus COGS. It is not net income, EBITDA, or a tax calculation.
- **Gross margin:** gross profit divided by net revenue; `null` when revenue is zero. It is a ratio of sums rather than an average of row percentages.
- **Customer concentration:** largest customer's net revenue / total annual net revenue.
- **Outstanding receivables:** provided invoice balance after credits and payments. Only positive balances are included. Current means days overdue <= 0; overdue means > 0. Buckets use inclusive upper bounds of 30, 60, and 90 days.
- **Inventory exception:** on-hand units <= reorder point on 2025-12-31. Exception-table value is on-hand units × product unit cost. Reorder points are synthetic input rules, not optimized recommendations.

## Forecast baseline and leakage controls

Train on all 12 months of **2024**, and hold out all 12 months of **2025**. Seasonal naive predicts a holdout month using the same calendar month in 2024. The comparator predicts every holdout month using the fixed mean of 2024's monthly revenue. The mean prediction is rounded to integer cents. Neither predictor uses 2025 values.

Return all holdout predictions and actuals, mean absolute error (MAE), and weighted absolute percentage error (WAPE = sum absolute errors / sum absolute actuals). WAPE is `null` if all actual revenue is zero. The analysis refuses to run if any required month lacks observations. It does not select a winner using the holdout and then claim an unbiased new evaluation.

This is a transparent statistical backtest, not a live AI forecast or a promise about future revenue. One training year is insufficient for strong generalization claims, and synthetic accuracy does not establish performance on client data.

## Correctness and security evidence

The independent test fixture uses five hand-specified sales events, including a signed return and a separate year. Its expected annual net revenue is 33,000 cents, gross profit 19,200 cents, and gross margin 58.1818%. Tests assert exact tables for monthly, category, product, customer, and region breakdowns. Aging tests check boundary days 0, 1, 30, 31, 60, 61, 90, and 91, partial payments/credits, and settled-invoice exclusion. Inventory tests include equality at reorder point and a non-current snapshot.

The suite includes **35 supported question variants** with independent numeric expectations and **31 rejection/clarification scenarios**, rather than merely checking that an answer exists. Additional tests cover empty data, zero denominators, a missing database, malicious instructions stored as a customer name, and unchanged database bytes after prohibited inputs. Forecast tests use a separate hand-calculated history and prove that changing holdout actuals changes error metrics without changing predictions.

Security comes from fixed application-owned SQL, parameterized year boundaries, a database opened in `mode=ro`, `query_only`, and an instruction-budget interrupt. User questions never become executable SQL. The vocabulary and injection checks supplement that separation; they are not a general-purpose prompt-injection firewall. No LLM consumes customer text. No live LLM/provider integration is implemented or implied.

## Honest portfolio description

> Built a governed analytics demonstration for a fictional distributor, covering revenue, gross margin, customer concentration, overdue receivables, and inventory exceptions. Implemented a read-only question interface with explicit metric definitions and independently tested financial calculations. Added a seasonal-naive revenue forecasting backtest with a temporal holdout, baseline comparison, and leakage tests. All data is synthetic; the interface is rules based rather than a live LLM.

Screenshots should show the synthetic-data and mode labels. Demonstrate a normal revenue answer, an aging table, a forecasting evaluation, and an unsupported question. Add real client details only after verifying scope, contribution, permission, and evidence separately.
