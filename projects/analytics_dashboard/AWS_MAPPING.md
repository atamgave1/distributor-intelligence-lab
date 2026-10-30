# Future AWS deployment design — not deployed

**Current evidence:** local Python/SQLite metrics and a browser dashboard. **Not current evidence:** Athena query runs, S3 objects, QuickSight datasets, workbooks, dashboards, refresh schedules or screenshots. There is no cloud access or approved spending budget for this phase.

## Intended flow

```text
Deterministic synthetic generator
    ├── Local SQLite → metrics.py → local browser dashboard [implemented]
    └── Explicit Parquet export [future work]
          → private S3 prefixes
          → Athena catalog tables / reporting views
          → QuickSight datasets
          → QuickSight dashboard [future work]
```

## Export contract

The current shared export consists of CSV source tables. `athena.sql` deliberately assumes an **additional Parquet export step**, which has not been implemented by this project. Do not upload the CSV exports to these prefixes and expect them to work as Parquet. A later exporter must preserve integer cents as 64-bit integers, UTF-8 strings, explicit `YYYY-MM-DD` date strings and the exact column names below, and must reconcile exported totals against the local snapshot before proceeding.

| Cloud prefix | Local source / grain | Required preparation |
|---|---|---|
| `reporting/sales/` | `v_sales`, one sales or return event | Materialize enriched events, not the grouped API cube |
| `reporting/receivables/` | `v_receivables`, one invoice as of 2025-12-31 | Include `as_of_date`; positive and settled rows may be exported, with dashboard filtering applied later |
| `reporting/inventory/` | inventory joined to products, one product/snapshot | Include product name, category and catalog cost; calculate value in SQL |

Reference S3 URI placeholders in SQL are not real bucket locations. Pick an account-owned bucket and region during a future authorized implementation. For this small demonstration, unpartitioned reporting tables keep the design simple. Introduce year/month partitions only after deciding the data layout; never claim partition pruning for this unpartitioned template.

## Athena and QuickSight work remaining

1. Approve a sandbox, AWS region, explicit spend cap and permitted resources. Use temporary role access rather than shared long-lived credentials.
2. Implement and test a Parquet exporter, create private storage and catalog resources, and configure Athena query-result storage and a dedicated workgroup.
3. Replace SQL placeholders. Run DDL, validate row counts, sums and schema against local references, and confirm return handling and snapshot cutoff.
4. Create separate QuickSight datasets for sales, invoice snapshots and inventory. Do not join all three at row level: that would multiply financial values. Use appropriate shared filter controls only where the dataset has matching dimensions.
5. Configure the actual QuickSight calculations: `sum(gross_profit_cents) / sum(net_revenue_cents)` with explicit zero-denominator handling; do not sum row-level margins. Apply cent-to-dollar conversions exactly once.
6. Choose and document direct-query or SPICE behavior. If SPICE is used, verify actual import and refresh behavior; neither is configured here.
7. Reconcile each visual and filter state against independent SQL expected values, test permissions, capture actual cloud screenshots, and publish measured evidence.
8. Record and review costs; remove test resources when finished. Athena workgroup scan controls and budget alerts should be considered, but alerts do not guarantee a hard total-spend cap. Do not initiate billing resources without an approved budget.

## Dashboard mapping

| Local component | Future QuickSight visual |
|---|---|
| Net revenue / gross profit cards | KPI visuals with currency formatting |
| Weighted margin / credit rate | Aggregate calculated fields with denominator guards |
| Monthly revenue and profit | Clustered bar chart by event month |
| Category / customer contribution | Horizontal bar charts |
| Receivables aging | Aging bucket calculated field and bar chart |
| Collections watchlist | Invoice-level table sorted by open overdue balance |
| Inventory exposure | Inventory dataset KPIs and low-stock count |

The local CSS and SVG layout is not directly importable as a QuickSight workbook. A real QuickSight workbook must be built, deployed, and reviewed separately.
