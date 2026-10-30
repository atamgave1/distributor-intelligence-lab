# Portfolio case study draft — Synthetic distributor analytics

**Independent synthetic demonstration. Local implementation. Not an actual client dataset, deliverable or AWS deployment.**

## Business scenario

A fictional distributor needs a consistent view of growth, margins, returns, overdue receivables and inventory. Its generated two-year dataset represents an illustrative mid-market business and contains intentionally seeded commercial scenarios. It is not reconstructed from a real organization.

## Implementation

Built a local reporting application using Python, SQLite, vanilla JavaScript and SVG. The shared dataset combines sales, return credits, customer and product attributes, invoices, allocated payments and inventory snapshots. The reporting model preserves transaction grain and aggregates signed return events into monthly, category and customer measures.

The executive page supports sales-period, customer-segment, region and product-category filters. It presents net revenue, gross profit, weighted gross margin and a value-based return-credit rate, with monthly exact-value tables. Separate snapshot panels show receivables aging, the largest overdue invoices and inventory exposure. The UI makes filter scope and metric definitions visible to avoid confusing historical sales filters with fixed-date balances.

## Engineering decisions

- Retain monetary values as integer cents until display formatting.
- Recognize return credits on their event date and reverse related cost.
- Calculate gross margin from aggregated profit and revenue, rather than averaging percentages.
- Use the already-reconciled invoice snapshot without joining it to individual sales lines.
- Explicitly treat invoices due on the reporting date as current.
- Read the reporting database through a read-only connection; the browser cannot submit SQL.
- Keep the implementation dependency-free and label all generated data as synthetic.

## Evidence to attach after verification

1. Executive overview with the full-year 2025 selection.
2. A filtered category/segment example showing changed results.
3. Working-capital panels and collections watchlist.
4. A concise architecture diagram and automated test report.

The screenshots must show the synthetic/local status labels. Do not crop these labels away to imply they are actual client screenshots or QuickSight evidence.

## Results that may be claimed

The artifact demonstrates reproducible data preparation, tested KPI calculations, interactive filters, dashboard presentation and transparent financial definitions. Attach actual test results and observed measurements only after the release checks run. No client revenue uplift, hours saved, production runtime or AWS cost reduction has been measured by this demonstration.

## Relationship to previous client experience

The user has an Upwork contract titled **“Data Engineer for AWS QuickSight & Athena”** with positive client feedback. This demonstration is separate. Any description of responsibilities, client outcomes or actual cloud architecture from that engagement must be supplied and approved by the user. Do not infer those details from this local code.

## Future AWS path

The mapping document and Athena SQL provide an implementation starting point for S3, Athena and QuickSight. They have not been deployed or integration-tested. A future cloud case study may describe those services as implemented only after actual deployment, reconciliation, refresh and evidence capture.
