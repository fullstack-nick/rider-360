select * except(source_updated_at), source_updated_at
from {{ source('raw', 'marketing_spend') }}
qualify row_number() over (
  partition by spend_date, site_market, campaign_id order by source_updated_at desc
) = 1
