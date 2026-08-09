select
  oi.order_id,
  sum(coalesce(r.refund_amount, 0)) as refund_amount,
  sum(coalesce(r.processing_cost, 0)) as return_processing_cost,
  countif(r.return_id is not null) as returned_line_count,
  countif(r.reason = 'size_not_right') as size_return_line_count,
  max(r.requested_at) as latest_return_requested_at
from {{ ref('stg_order_items') }} oi
left join {{ ref('stg_returns') }} r using (order_item_id)
group by oi.order_id
