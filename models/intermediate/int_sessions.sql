with event_rollup as (
  select
    session_key,
    any_value(user_pseudo_id having min event_at) as user_pseudo_id,
    any_value(user_id having max event_at) as user_id,
    min(event_at) as session_started_at,
    max(event_at) as session_ended_at,
    any_value(site_market having min event_at) as site_market,
    any_value(device_category having min event_at) as device_category,
    any_value(session_source having min event_at) as source,
    any_value(session_medium having min event_at) as medium,
    any_value(session_campaign_id having min event_at) as campaign_id,
    count(*) as event_count,
    countif(event_name = 'view_item') > 0 as viewed_product,
    countif(event_name = 'size_path_open') > 0 as used_size_path,
    countif(event_name = 'add_to_cart') > 0 as added_to_cart,
    countif(event_name = 'begin_checkout') > 0 as began_checkout,
    countif(event_name = 'add_shipping_info') > 0 as added_shipping_info,
    countif(event_name = 'add_payment_info') > 0 as added_payment_info,
    countif(event_name = 'purchase') > 0 as purchased
  from {{ ref('stg_events') }}
  where session_key is not null
  group by session_key
)
select
  *,
  date(session_started_at, 'Europe/Vienna') as session_date,
  case
    when source = 'search' and medium = 'organic' then 'Organic Search'
    when source = 'search_ads' and medium = 'cpc' then 'Paid Search'
    when source = 'social_ads' and medium = 'paid_social' then 'Paid Social'
    when medium = 'email' then 'Email'
    when medium = 'affiliate' then 'Affiliate'
    when source = '(direct)' then 'Direct'
    else 'Other'
  end as channel
from event_rollup
