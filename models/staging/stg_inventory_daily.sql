select * except(source_updated_at), source_updated_at
from {{ source('raw', 'inventory_daily') }}
qualify row_number() over (
  partition by inventory_date, site_market, sku order by source_updated_at desc
) = 1
