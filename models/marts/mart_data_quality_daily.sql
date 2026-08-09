with event_quality as (
  select
    event_date as metric_date,
    site_market,
    count(*) as event_rows,
    countif(event_name = 'purchase') as purchase_event_rows,
    countif(event_name = 'purchase' and transaction_id is null) as purchases_missing_transaction_id,
    countif(event_name = 'size_path_recommendation') as recommendation_events,
    countif(event_name = 'size_path_recommendation' and recommended_product_id is null) as recommendations_missing_product,
    countif(timestamp_diff(arrived_at, event_at, hour) > 24) as late_events
  from {{ ref('stg_events') }}
  group by 1, 2
), fx_quality as (
  select date(placed_at) as metric_date, site_market, countif(fx_to_eur is null) as orders_missing_fx
  from {{ ref('int_orders_enriched') }}
  group by 1, 2
)
select
  e.*,
  coalesce(f.orders_missing_fx, 0) as orders_missing_fx,
  safe_divide(recommendations_missing_product, recommendation_events) as recommendation_parameter_missing_rate
from event_quality e
left join fx_quality f using (metric_date, site_market)
