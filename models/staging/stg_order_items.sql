select * except(source_updated_at), source_updated_at
from {{ source('raw', 'order_items') }}
qualify row_number() over (partition by order_item_id order by source_updated_at desc) = 1
