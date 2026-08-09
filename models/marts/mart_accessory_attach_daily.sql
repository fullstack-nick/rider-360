with bike_orders as (
  select
    order_id,
    date(placed_at, 'Europe/Vienna') as metric_date,
    site_market,
    sku as parent_sku,
    product_name as parent_product,
    family as parent_family,
    wheel_size
  from {{ ref('int_order_items_enriched') }}
  where category = 'bike'
), compatible_accessories as (
  select
    b.*,
    countif(a.category = 'accessory') as attached_accessory_lines,
    countif(c.accessory_sku is not null) as compatible_accessory_lines
  from bike_orders b
  left join {{ ref('int_order_items_enriched') }} a using (order_id)
  left join {{ ref('stg_compatibility') }} c
    on c.parent_sku = b.parent_sku
    and c.accessory_sku = a.sku
    and b.metric_date between c.valid_from and coalesce(c.valid_to, date '9999-12-31')
  group by all
)
select
  metric_date,
  site_market,
  parent_sku,
  parent_product,
  parent_family,
  wheel_size,
  count(*) as bike_orders,
  countif(attached_accessory_lines > 0) as orders_with_any_accessory,
  countif(compatible_accessory_lines > 0) as orders_with_compatible_accessory,
  safe_divide(countif(compatible_accessory_lines > 0), count(*)) as compatible_attach_rate
from compatible_accessories
group by 1, 2, 3, 4, 5, 6
