-- FUTURE TEMPLATE ONLY. Not executed or integration-tested against AWS.
-- Replace REPLACE_WITH_BUCKET. Requires NEW Parquet exports of the reporting
-- views, not the currently generated CSV files. See AWS_MAPPING.md.
-- Date strings are retained as ISO strings and converted explicitly in views.

CREATE DATABASE IF NOT EXISTS portfolio_demo;

CREATE EXTERNAL TABLE IF NOT EXISTS portfolio_demo.sales_events (
  event_id string,
  event_date string,
  order_id string,
  customer_id string,
  product_id string,
  net_revenue_cents bigint,
  cogs_cents bigint,
  units bigint,
  kind string,
  customer_name string,
  segment string,
  region string,
  product_name string,
  category string
)
STORED AS PARQUET
LOCATION 's3://REPLACE_WITH_BUCKET/reporting/sales/';

CREATE EXTERNAL TABLE IF NOT EXISTS portfolio_demo.receivable_snapshots (
  as_of_date string,
  invoice_id string,
  customer_id string,
  customer_name string,
  segment string,
  region string,
  invoice_date string,
  due_date string,
  invoice_amount_cents bigint,
  credit_cents bigint,
  paid_cents bigint,
  outstanding_cents bigint,
  days_overdue bigint
)
STORED AS PARQUET
LOCATION 's3://REPLACE_WITH_BUCKET/reporting/receivables/';

CREATE EXTERNAL TABLE IF NOT EXISTS portfolio_demo.inventory_snapshots (
  snapshot_date string,
  product_id string,
  sku string,
  product_name string,
  category string,
  on_hand_units bigint,
  reorder_point bigint,
  unit_cost_cents bigint
)
STORED AS PARQUET
LOCATION 's3://REPLACE_WITH_BUCKET/reporting/inventory/';

CREATE OR REPLACE VIEW portfolio_demo.monthly_sales AS
SELECT date_trunc('month', CAST(event_date AS date)) AS event_month,
       segment, region, category,
       SUM(net_revenue_cents) AS net_revenue_cents,
       SUM(net_revenue_cents - cogs_cents) AS gross_profit_cents,
       SUM(CASE WHEN net_revenue_cents > 0 THEN net_revenue_cents ELSE 0 END) AS gross_sales_cents,
       -SUM(CASE WHEN net_revenue_cents < 0 THEN net_revenue_cents ELSE 0 END) AS return_credit_cents,
       CAST(SUM(net_revenue_cents - cogs_cents) AS double)
         / NULLIF(SUM(net_revenue_cents), 0) AS gross_margin_ratio
FROM portfolio_demo.sales_events
WHERE CAST(event_date AS date) <= DATE '2025-12-31'
GROUP BY 1, 2, 3, 4;

CREATE OR REPLACE VIEW portfolio_demo.aging AS
SELECT invoice_id, customer_id, customer_name, segment, region,
       invoice_date, due_date, outstanding_cents, days_overdue,
       CASE WHEN days_overdue <= 0 THEN 'Current'
            WHEN days_overdue <= 30 THEN '1-30 days'
            WHEN days_overdue <= 60 THEN '31-60 days'
            WHEN days_overdue <= 90 THEN '61-90 days'
            ELSE '91+ days' END AS aging_bucket
FROM portfolio_demo.receivable_snapshots
WHERE as_of_date = '2025-12-31' AND outstanding_cents > 0;

CREATE OR REPLACE VIEW portfolio_demo.latest_inventory AS
SELECT snapshot_date, product_id, sku, product_name, category,
       on_hand_units, reorder_point,
       on_hand_units * unit_cost_cents AS stock_value_cents,
       on_hand_units <= reorder_point AS at_or_below_reorder_point
FROM portfolio_demo.inventory_snapshots
WHERE snapshot_date = (
  SELECT MAX(snapshot_date) FROM portfolio_demo.inventory_snapshots
  WHERE CAST(snapshot_date AS date) <= DATE '2025-12-31'
);

-- Example independent reconciliation query. Compare these exact sums to the
-- local model before any actual QuickSight workbook is accepted.
SELECT SUM(net_revenue_cents) AS net_revenue_cents,
       SUM(net_revenue_cents - cogs_cents) AS gross_profit_cents
FROM portfolio_demo.sales_events
WHERE CAST(event_date AS date) >= DATE '2025-01-01'
  AND CAST(event_date AS date) <= DATE '2025-12-31';
