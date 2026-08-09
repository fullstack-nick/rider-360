select * from {{ source('raw', 'exchange_rates') }}
qualify row_number() over (
  partition by rate_date, source_currency, reporting_currency order by loaded_at desc
) = 1
