select * from {{ ref('mart_funnel_daily') }}
where not (
  sessions >= product_view_sessions
  and product_view_sessions >= add_to_cart_sessions
  and add_to_cart_sessions >= checkout_sessions
  and checkout_sessions >= shipping_sessions
  and shipping_sessions >= payment_sessions
  and payment_sessions >= purchase_sessions
)
