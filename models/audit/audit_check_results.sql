with funnel as (
  select count(*) as failures
  from {{ ref('mart_funnel_daily') }}
  where not (
    sessions >= product_view_sessions
    and product_view_sessions >= add_to_cart_sessions
    and add_to_cart_sessions >= checkout_sessions
    and checkout_sessions >= shipping_sessions
    and shipping_sessions >= payment_sessions
    and payment_sessions >= purchase_sessions
  )
), economics as (
  select count(*) as failures
  from {{ ref('mart_executive_daily') }}
  where sessions < 0 or orders < 0 or revenue_eur < 0 or marketing_spend_eur < 0
), measurement as (
  select
    sum(purchases_missing_transaction_id + orders_missing_fx) as critical_failures,
    max(recommendation_parameter_missing_rate) as maximum_recommendation_missing_rate
  from {{ ref('mart_data_quality_daily') }}
), arrivals as (
  select sum(deliveries_over_30_minutes_late) as late_deliveries
  from {{ ref('audit_source_freshness') }}
)
select
  current_timestamp() as evaluated_at,
  'purchase_order_reconciliation' as check_name,
  if(purchases_without_orders = 0 and orders_without_purchases = 0, 'pass', 'fail') as status,
  cast(greatest(purchases_without_orders, orders_without_purchases) as numeric) as observed_value,
  cast(0 as numeric) as threshold,
  format(
    'purchases_without_orders=%d; orders_without_purchases=%d',
    purchases_without_orders,
    orders_without_purchases
  ) as details
from {{ ref('audit_reconciliation') }}

union all

select
  current_timestamp(),
  'funnel_monotonicity',
  if(failures = 0, 'pass', 'fail'),
  cast(failures as numeric),
  cast(0 as numeric),
  format('non-monotonic aggregate rows=%d', failures)
from funnel

union all

select
  current_timestamp(),
  'non_negative_commercial_metrics',
  if(failures = 0, 'pass', 'fail'),
  cast(failures as numeric),
  cast(0 as numeric),
  format('negative aggregate rows=%d', failures)
from economics

union all

select
  current_timestamp(),
  'critical_measurement_completeness',
  if(critical_failures = 0, 'pass', 'fail'),
  cast(critical_failures as numeric),
  cast(0 as numeric),
  format('missing transaction IDs or FX rows=%d', critical_failures)
from measurement

union all

select
  current_timestamp(),
  'recommendation_parameter_coverage',
  if(maximum_recommendation_missing_rate <= 0.10, 'pass', 'warning'),
  cast(maximum_recommendation_missing_rate as numeric),
  cast(0.10 as numeric),
  'warning threshold is 10% missing at the published market-day grain'
from measurement

union all

select
  current_timestamp(),
  'source_arrival_timeliness',
  if(late_deliveries = 0, 'pass', 'warning'),
  cast(late_deliveries as numeric),
  cast(0 as numeric),
  format('latest-partition deliveries over 30 minutes late=%d', late_deliveries)
from arrivals
