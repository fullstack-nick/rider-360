select
  order_id,
  customer_id,
  session_key,
  placed_at,
  paid_at,
  cancelled_at,
  source_updated_at,
  status,
  site_market,
  currency,
  gross_item_sales,
  item_discount,
  tax_amount,
  shipping_charged,
  order_total,
  payment_cost,
  fulfillment_cost
from {{ source('raw', 'orders') }}
where not is_test
qualify row_number() over (partition by order_id order by source_updated_at desc) = 1
