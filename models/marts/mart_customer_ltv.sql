with customer_orders as (
  select
    c.customer_id,
    c.first_order_date as cohort_date,
    c.acquisition_market,
    c.acquisition_channel,
    o.order_id,
    date(o.placed_at) as order_date,
    o.net_item_revenue_eur - o.variable_cost_eur as contribution_margin_eur
  from {{ ref('stg_customers') }} c
  join {{ ref('int_orders_enriched') }} o using (customer_id)
)
select
  date_trunc(cohort_date, month) as cohort_month,
  acquisition_market,
  acquisition_channel,
  count(distinct customer_id) as customers,
  count(distinct order_id) as lifetime_orders,
  sum(contribution_margin_eur) as observed_contribution_margin_eur,
  sum(if(date_diff(order_date, cohort_date, day) <= 90, contribution_margin_eur, 0)) as contribution_margin_90d_eur,
  sum(if(date_diff(order_date, cohort_date, day) <= 365, contribution_margin_eur, 0)) as contribution_margin_365d_eur,
  safe_divide(sum(contribution_margin_eur), count(distinct customer_id)) as contribution_ltv_per_customer_eur,
  safe_divide(count(distinct order_id), count(distinct customer_id)) as orders_per_customer
from customer_orders
group by 1, 2, 3
