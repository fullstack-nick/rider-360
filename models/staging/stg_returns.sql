select * except(source_updated_at), source_updated_at
from {{ source('raw', 'returns') }}
qualify row_number() over (partition by return_id order by source_updated_at desc) = 1
