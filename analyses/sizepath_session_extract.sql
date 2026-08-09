-- One row per pre-treatment eligible product-view session.
-- BigQuery is authoritative; the extract contains no latent-intent fields.
with session_history as (
  select
    session_key,
    user_pseudo_id,
    session_started_at,
    session_date,
    site_market,
    device_category,
    channel,
    used_size_path,
    purchased,
    count(*) over (
      partition by user_pseudo_id
      order by session_started_at, session_key
      rows between unbounded preceding and 1 preceding
    ) as prior_session_count,
    countif(purchased) over (
      partition by user_pseudo_id
      order by session_started_at, session_key
      rows between unbounded preceding and 1 preceding
    ) as prior_purchase_count
  from `{project_id}.r360_intermediate.int_sessions`
  where viewed_product
), first_product as (
  select
    session_key,
    any_value(item.item_id having min event_at) as viewed_sku
  from `{project_id}.r360_staging.stg_events`, unnest(items) as item
  where event_name = 'view_item'
  group by session_key
)
select
  s.session_key,
  s.user_pseudo_id,
  s.session_started_at,
  s.session_date,
  s.site_market,
  s.device_category,
  s.channel,
  coalesce(p.viewed_sku, 'unknown') as viewed_sku,
  extract(hour from s.session_started_at at time zone 'Europe/Vienna') as session_hour,
  extract(dayofweek from s.session_date) as day_of_week,
  format_date('%Y-%m', s.session_date) as year_month,
  least(s.prior_session_count, 10) as prior_session_count,
  s.prior_purchase_count > 0 as prior_purchaser,
  cast(s.used_size_path as int64) as treatment,
  cast(s.purchased as int64) as outcome
from session_history s
left join first_product p using (session_key)
