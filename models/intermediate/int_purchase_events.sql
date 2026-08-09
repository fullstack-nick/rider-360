select
  transaction_id,
  session_key,
  user_pseudo_id,
  user_id,
  event_at as purchased_at,
  site_market,
  event_currency as currency,
  event_value,
  collected_source,
  collected_medium,
  session_source,
  session_medium
from {{ ref('stg_events') }}
where event_name = 'purchase' and transaction_id is not null
qualify row_number() over (partition by transaction_id order by event_at, event_id) = 1
