with source as (
  select * from {{ source('raw', 'events') }}
), typed as (
  select
    event_date,
    timestamp_micros(event_timestamp) as event_at,
    event_name,
    event_id,
    event_bundle_sequence_id,
    user_pseudo_id,
    user_id,
    {{ event_param_string('session_key') }} as session_key,
    {{ event_param_int('ga_session_id') }} as ga_session_id,
    {{ event_param_string('transaction_id') }} as transaction_id,
    {{ event_param_string('currency') }} as event_currency,
    {{ event_param_numeric('value') }} as event_value,
    {{ event_param_string('size_path_version') }} as size_path_version,
    {{ event_param_string('recommended_product_id') }} as recommended_product_id,
    stream_id,
    platform,
    device_category,
    browser,
    geo_country as site_market,
    privacy_analytics_storage,
    traffic_source_source as first_user_source,
    traffic_source_medium as first_user_medium,
    traffic_source_campaign as first_user_campaign,
    collected_source,
    collected_medium,
    collected_campaign_id,
    session_source,
    session_medium,
    session_campaign_id,
    items,
    source_kind,
    source_updated_at,
    arrived_at
  from source
)
select * from typed
qualify row_number() over (partition by event_id order by arrived_at desc) = 1
