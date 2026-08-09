with orders_with_fx as (
  select
    o.*,
    fx.rate as fx_to_eur,
    fx.provider_date as fx_provider_date
  from {{ ref('stg_orders') }} o
  left join {{ ref('stg_exchange_rates') }} fx
    on fx.source_currency = o.currency
    and fx.reporting_currency = 'EUR'
    and fx.rate_date between date_sub(date(o.placed_at), interval 7 day) and date(o.placed_at)
  qualify row_number() over (
    partition by o.order_id
    order by fx.rate_date desc nulls last
  ) = 1
)

select
  o.*,
  s.session_started_at,
  s.channel,
  s.source,
  s.medium,
  s.device_category,
  s.used_size_path,
  coalesce(r.refund_amount, 0) as refund_amount,
  coalesce(r.return_processing_cost, 0) as return_processing_cost,
  coalesce(r.returned_line_count, 0) as returned_line_count,
  coalesce(r.size_return_line_count, 0) as size_return_line_count,
  date_diff(date(o.placed_at), o.fx_provider_date, day) as fx_age_days,
  safe_divide(o.order_total, 100) * o.fx_to_eur as revenue_eur,
  safe_divide(o.gross_item_sales - o.item_discount - coalesce(r.refund_amount, 0), 100) * o.fx_to_eur as net_item_revenue_eur,
  safe_divide(o.payment_cost + o.fulfillment_cost + coalesce(r.return_processing_cost, 0), 100) * o.fx_to_eur as variable_cost_eur
from orders_with_fx o
left join {{ ref('int_sessions') }} s using (session_key)
left join {{ ref('int_order_returns') }} r using (order_id)
