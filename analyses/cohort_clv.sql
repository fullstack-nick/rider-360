-- Mature cohorts only: acquisition quality after a full 365-day observation window.
select
  acquisition_channel,
  sum(customers) as customers,
  sum(contribution_margin_365d_eur) as contribution_margin_365d_eur,
  safe_divide(sum(contribution_margin_365d_eur), sum(customers)) as contribution_365d_per_customer_eur,
  safe_divide(sum(lifetime_orders), sum(customers)) as orders_per_customer
from `{project_id}.r360_marts.mart_customer_ltv`
where cohort_month <= date_sub(date '2025-12-31', interval 365 day)
group by acquisition_channel
order by contribution_365d_per_customer_eur desc
