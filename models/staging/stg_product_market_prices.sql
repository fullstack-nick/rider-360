select * from {{ source('raw', 'product_market_prices') }}
qualify row_number() over (partition by price_version_id order by valid_from desc) = 1
