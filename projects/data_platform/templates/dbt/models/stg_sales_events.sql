-- OPTIONAL / NOT EXECUTED. PostgreSQL or Redshift raw schema, not SQLite ATTACH.
select event_id, event_date, order_id, customer_id, product_id,
       net_revenue_cents, cogs_cents, units, kind,
       customer_name, segment, region, product_name, category
from {{ source('raw', 'sales_events') }}
where is_deleted = 0
