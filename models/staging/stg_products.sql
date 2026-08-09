select * from {{ source('raw', 'products') }}
qualify row_number() over (partition by product_version_id order by valid_from desc) = 1
