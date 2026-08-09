select
  i.inventory_date as metric_date,
  i.site_market,
  i.sku,
  p.product_name,
  p.category,
  p.family,
  p.wheel_size,
  i.beginning_ats,
  i.receipts,
  i.units_reserved,
  i.units_sold,
  i.ending_ats,
  i.stockout_minutes,
  i.stock_status,
  safe_divide(i.stockout_minutes, 1440) as stockout_day_fraction
from {{ ref('stg_inventory_daily') }} i
left join {{ ref('stg_products') }} p
  on i.sku = p.sku
  and i.inventory_date between p.valid_from and coalesce(p.valid_to, date '9999-12-31')
