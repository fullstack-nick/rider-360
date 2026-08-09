-- Fixed, pre-specified eight-week windows around the planted FR mobile payment release.
select
  case
    when site_market = 'FR' and device_category = 'mobile' then 'FR mobile'
    when site_market = 'FR' and device_category = 'desktop' then 'FR desktop'
    when site_market in ('DE', 'NL') and device_category = 'mobile' then 'DE/NL mobile control'
    else 'other'
  end as segment,
  case
    when metric_date between date '2025-01-13' and date '2025-03-09' then 'pre'
    when metric_date between date '2025-03-10' and date '2025-05-04' then 'post'
  end as period,
  sum(payment_sessions) as payment_sessions,
  sum(purchase_sessions) as purchase_sessions,
  safe_divide(sum(purchase_sessions), sum(payment_sessions)) as payment_to_purchase_rate
from `{project_id}.r360_marts.mart_funnel_daily`
where metric_date between date '2025-01-13' and date '2025-05-04'
group by 1, 2
having segment != 'other'
order by segment, period
