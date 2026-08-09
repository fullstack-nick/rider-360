select * from {{ source('raw', 'product_accessory_compatibility') }}
qualify row_number() over (partition by compatibility_id order by valid_from desc) = 1
