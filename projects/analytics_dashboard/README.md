# Revenue, margin & working-capital dashboard

**Synthetic demonstration · local prototype · AWS deployment pending.**

Northstar Distribution is a fictional distributor, not a client. The portfolio lab generates its data reproducibly under the shared `docs/DATA_CONTRACT.md` (v1.0.0). No private customer records or client screenshots are used. This implementation is vanilla HTML/CSS/JavaScript, SQLite and Python; it is **not a deployed Athena/QuickSight dashboard**.

## What this demonstrates

- A concise management view of net revenue, gross profit, weighted margin and value-based return credits.
- Monthly comparisons, category contributions and top customers, with real year, segment, region and category filters.
- Receivables aging and an actionable top-eight overdue invoice watchlist.
- Latest-snapshot inventory value and products at or below fictional reorder thresholds.
- Explicit data grain, cent-based arithmetic, signed return events and documented filter scope.
- Accessible exact monthly values alongside SVG charts, semantic tables, native keyboard controls, responsive layout and no external scripts, fonts or CDNs.

## Run

Use the portfolio lab's root server and open **`/dashboard`**. The server supplies `GET /api/dashboard` by calling `metrics.dashboard(db_path)`. It must also serve this folder's `styles.css` and `app.js` at `/dashboard/styles.css` and `/dashboard/app.js`. Running `index.html` directly from disk will not provide the reporting API.

The Python API reads the database in SQLite read-only mode. The browser does not submit SQL; filters operate on a pre-aggregated dimension cube. The full cube is intentionally suitable for a synthetic local demo, not a model for exposing sensitive client datasets to browsers. A production version needs authenticated, authorized, server-side queries and appropriate row-level access rules.

## Filter scope

| Filter | Sales | Receivables | Inventory |
|---|---|---|---|
| Sales year | Event date | No: fixed 2025-12-31 snapshot | No: latest snapshot through cutoff |
| Segment / region | Customer attributes | Customer attributes | No: warehouse stock is not customer-owned |
| Category | Product category | No: open invoice may span categories | Product category |

Snapshot scope is displayed in the UI. Changing the sales year must not falsely reconstruct historical receivables. Due-today invoices are current, and only positive outstanding balances enter aging. The final aging bucket is labeled `90+ days` for compact display and means **strictly more than 90 days**, equivalent to 91+ in the shared contract.

## Verification

From the repository root:

```sh
python3 -m unittest discover -s projects/analytics_dashboard -p 'test_metrics.py' -v
node projects/analytics_dashboard/test_frontend.js
```

The Python tests use hand-calculated fixtures independent of the generator and check signed returns, weighted margins, partial payments, due-today and every aging boundary, future-event exclusion, inventory snapshot selection, empty results and zero denominators. The JavaScript tests exercise the actual filter and aggregation functions used by the page. Browser checks should additionally verify layout, select interactions, reset behavior, empty-state rendering and accessibility.

## Files

- `metrics.py`: read-only SQL aggregation and reporting contract.
- `index.html`, `styles.css`, `app.js`: dependency-free browser dashboard.
- `test_metrics.py`, `test_frontend.js`: independent correctness checks.
- `CASE_STUDY.md`: truthful case-study draft for this synthetic implementation.
- `AWS_MAPPING.md`, `athena.sql`: future-cloud design templates, not deployed assets or claims of cloud validation.

## Known limits

No live AWS resources, QuickSight workbook, authentication, scheduled refresh, arbitrary historical snapshot reconstruction or production benchmark is included. There is no demand forecasting: low-stock counts compare on-hand quantity to a synthetic policy threshold. Gross profit excludes overhead and must not be described as net profit. Figures and scenario findings are illustrative and cannot be represented as client business outcomes.
