select * except(source_updated_at), source_updated_at
from {{ source('raw', 'customers') }}
qualify row_number() over (partition by customer_id order by source_updated_at desc) = 1
