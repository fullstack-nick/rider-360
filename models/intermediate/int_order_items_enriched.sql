select
  oi.*,
  p.product_name,
  p.category,
  p.family,
  p.wheel_size,
  o.site_market,
  o.placed_at,
  o.session_key,
  s.channel,
  s.used_size_path,
  r.reason as return_reason,
  r.refund_amount,
  r.processing_cost as return_processing_cost,
  r.requested_at as return_requested_at
from {{ ref('stg_order_items') }} oi
join {{ ref('stg_orders') }} o using (order_id)
left join {{ ref('stg_products') }} p
  on oi.sku = p.sku
  and date(o.placed_at) between p.valid_from and coalesce(p.valid_to, date '9999-12-31')
left join {{ ref('int_sessions') }} s using (session_key)
left join {{ ref('stg_returns') }} r using (order_item_id)
