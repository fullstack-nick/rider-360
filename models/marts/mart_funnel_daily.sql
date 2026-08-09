select
  session_date as metric_date,
  site_market,
  device_category,
  channel,
  count(*) as sessions,
  countif(viewed_product) as product_view_sessions,
  countif(added_to_cart) as add_to_cart_sessions,
  countif(began_checkout) as checkout_sessions,
  countif(added_shipping_info) as shipping_sessions,
  countif(added_payment_info) as payment_sessions,
  countif(purchased) as purchase_sessions,
  safe_divide(countif(added_to_cart), countif(viewed_product)) as view_to_cart_rate,
  safe_divide(countif(began_checkout), countif(added_to_cart)) as cart_to_checkout_rate,
  safe_divide(countif(purchased), countif(added_payment_info)) as payment_to_purchase_rate,
  safe_divide(countif(purchased), count(*)) as session_conversion_rate
from {{ ref('int_sessions') }}
group by 1, 2, 3, 4
