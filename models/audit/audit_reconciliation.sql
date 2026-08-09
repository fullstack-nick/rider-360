select
  current_timestamp() as audited_at,
  (select count(*) from {{ ref('int_purchase_events') }}) as distinct_purchase_transactions,
  (select count(*) from {{ ref('stg_orders') }}) as operational_orders,
  (select count(*) from {{ ref('int_purchase_events') }} p left join {{ ref('stg_orders') }} o on p.transaction_id = o.order_id where o.order_id is null) as purchases_without_orders,
  (select count(*) from {{ ref('stg_orders') }} o left join {{ ref('int_purchase_events') }} p on o.order_id = p.transaction_id where p.transaction_id is null) as orders_without_purchases,
  (select count(*) from {{ ref('int_orders_enriched') }} where fx_to_eur is null) as orders_missing_fx
