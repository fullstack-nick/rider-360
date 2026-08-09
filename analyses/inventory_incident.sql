-- Operational evidence for the planted Comet 16 stockout window.
select
  site_market,
  case
    when metric_date between date '2025-04-14' and date '2025-05-11' then 'pre'
    when metric_date between date '2025-05-12' and date '2025-06-08' then 'incident'
  end as period,
  count(*) as product_days,
  sum(units_sold) as units_sold,
  avg(stockout_day_fraction) as average_stockout_day_fraction,
  countif(stock_status = 'out_of_stock') as out_of_stock_days
from `{project_id}.r360_marts.mart_inventory_daily`
where sku = 'R360-B16-COMET'
  and site_market in ('AT', 'DE')
  and metric_date between date '2025-04-14' and date '2025-06-08'
group by 1, 2
order by site_market, period
