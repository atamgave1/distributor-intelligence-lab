-- OPTIONAL / NOT EXECUTED. Add an environment-specific adapter and run dbt build.
select event_date,
       sum(net_revenue_cents) as net_revenue_cents,
       sum(cogs_cents) as cogs_cents,
       sum(net_revenue_cents - cogs_cents) as gross_margin_cents,
       sum(units) as units,
       count(*) as event_count
from {{ ref('stg_sales_events') }}
group by event_date
