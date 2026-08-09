-- Compatibility-aware attach gap for the two deliberately under-merchandised bikes.
with product_rates as (
  select
    parent_sku,
    any_value(parent_product) as parent_product,
    any_value(wheel_size) as wheel_size,
    sum(bike_orders) as bike_orders,
    sum(orders_with_compatible_accessory) as attached_orders,
    safe_divide(sum(orders_with_compatible_accessory), sum(bike_orders)) as attach_rate
  from `{project_id}.r360_marts.mart_accessory_attach_daily`
  where metric_date >= date '2024-01-01'
  group by parent_sku
), paired as (
  select
    affected.parent_sku,
    affected.parent_product,
    affected.bike_orders,
    affected.attached_orders,
    affected.attach_rate,
    avg(peer.attach_rate) as peer_attach_rate
  from product_rates affected
  join product_rates peer
    on peer.wheel_size = affected.wheel_size
    and peer.parent_sku != affected.parent_sku
  where affected.parent_sku in ('R360-B20-DRIFT', 'R360-B24-RIDGE')
  group by 1, 2, 3, 4, 5
)
select
  *,
  greatest(peer_attach_rate - attach_rate, 0) as attach_rate_gap,
  bike_orders * greatest(peer_attach_rate - attach_rate, 0) as incremental_attach_orders
from paired
order by incremental_attach_orders desc
