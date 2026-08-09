with session_outcomes as (
  select
    s.session_date as metric_date,
    s.site_market,
    s.device_category,
    s.used_size_path,
    s.purchased,
    countif(o.size_return_line_count > 0) > 0 as had_size_return,
    countif(o.order_id is not null) > 0 as has_mature_order
  from {{ ref('int_sessions') }} s
  left join {{ ref('int_orders_enriched') }} o using (session_key)
  group by 1, 2, 3, 4, 5
)
select
  metric_date,
  site_market,
  device_category,
  used_size_path,
  count(*) as sessions,
  countif(purchased) as purchasing_sessions,
  countif(had_size_return) as size_return_sessions,
  countif(
    had_size_return
    and metric_date <= date_sub(current_date(), interval {{ var('return_maturity_days') }} day)
  ) as mature_size_return_sessions,
  countif(has_mature_order and metric_date <= date_sub(current_date(), interval {{ var('return_maturity_days') }} day)) as mature_order_sessions,
  safe_divide(countif(purchased), count(*)) as conversion_rate,
  safe_divide(
    countif(had_size_return and metric_date <= date_sub(current_date(), interval {{ var('return_maturity_days') }} day)),
    countif(has_mature_order and metric_date <= date_sub(current_date(), interval {{ var('return_maturity_days') }} day))
  ) as mature_size_return_rate
from session_outcomes
group by 1, 2, 3, 4
