-- Channel economics use contribution before and after marketing, not revenue-only ROAS.
select
  channel,
  sum(sessions) as sessions,
  sum(orders) as orders,
  sum(purchasing_customers) as purchasing_customers,
  sum(revenue_eur) as revenue_eur,
  sum(contribution_margin_eur) as contribution_margin_eur,
  sum(marketing_spend_eur) as marketing_spend_eur,
  sum(contribution_margin_eur) - sum(marketing_spend_eur) as contribution_after_marketing_eur,
  safe_divide(sum(orders), sum(sessions)) as conversion_rate,
  safe_divide(sum(marketing_spend_eur), sum(purchasing_customers)) as cac_eur,
  safe_divide(sum(contribution_margin_eur), sum(marketing_spend_eur)) as contribution_roas
from `{project_id}.r360_marts.mart_executive_daily`
group by channel
order by contribution_after_marketing_eur
