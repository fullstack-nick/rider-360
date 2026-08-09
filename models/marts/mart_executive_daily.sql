with sessions as (
  select
    session_date as metric_date,
    site_market,
    channel,
    count(*) as sessions,
    countif(added_to_cart) as add_to_cart_sessions,
    countif(began_checkout) as checkout_sessions,
    countif(purchased) as purchase_sessions
  from {{ ref('int_sessions') }}
  group by 1, 2, 3
), orders as (
  select
    date(placed_at, 'Europe/Vienna') as metric_date,
    site_market,
    coalesce(channel, 'Unknown') as channel,
    count(*) as orders,
    count(distinct customer_id) as purchasing_customers,
    sum(revenue_eur) as revenue_eur,
    sum(net_item_revenue_eur) as net_item_revenue_eur,
    sum(variable_cost_eur) as variable_cost_eur,
    sum(net_item_revenue_eur - variable_cost_eur) as contribution_margin_eur,
    sum(refund_amount / 100 * fx_to_eur) as refunds_eur
  from {{ ref('int_orders_enriched') }}
  group by 1, 2, 3
), spend as (
  select
    spend_date as metric_date,
    site_market,
    channel,
    sum(cost / 100 * fx.rate) as marketing_spend_eur
  from {{ ref('stg_marketing_spend') }} ms
  left join {{ ref('stg_exchange_rates') }} fx
    on fx.rate_date = ms.spend_date
    and fx.source_currency = ms.currency
    and fx.reporting_currency = 'EUR'
  group by 1, 2, 3
)
select
  coalesce(s.metric_date, o.metric_date, m.metric_date) as metric_date,
  coalesce(s.site_market, o.site_market, m.site_market) as site_market,
  coalesce(s.channel, o.channel, m.channel) as channel,
  coalesce(s.sessions, 0) as sessions,
  coalesce(s.add_to_cart_sessions, 0) as add_to_cart_sessions,
  coalesce(s.checkout_sessions, 0) as checkout_sessions,
  coalesce(s.purchase_sessions, 0) as purchase_sessions,
  coalesce(o.orders, 0) as orders,
  coalesce(o.purchasing_customers, 0) as purchasing_customers,
  coalesce(o.revenue_eur, 0) as revenue_eur,
  coalesce(o.net_item_revenue_eur, 0) as net_item_revenue_eur,
  coalesce(o.variable_cost_eur, 0) as variable_cost_eur,
  coalesce(o.contribution_margin_eur, 0) as contribution_margin_eur,
  coalesce(o.refunds_eur, 0) as refunds_eur,
  coalesce(m.marketing_spend_eur, 0) as marketing_spend_eur,
  safe_divide(o.orders, s.sessions) as session_conversion_rate,
  safe_divide(o.revenue_eur, o.orders) as average_order_value_eur,
  safe_divide(o.contribution_margin_eur - m.marketing_spend_eur, m.marketing_spend_eur) as marketing_roi
from sessions s
full join orders o using (metric_date, site_market, channel)
full join spend m using (metric_date, site_market, channel)
