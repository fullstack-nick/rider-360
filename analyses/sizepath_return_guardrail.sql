-- Descriptive only: purchase is post-treatment, so this is a guardrail, not a total causal effect.
select
  used_size_path,
  sum(mature_order_sessions) as mature_order_sessions,
  sum(size_return_sessions) as size_return_sessions,
  safe_divide(sum(size_return_sessions), sum(mature_order_sessions)) as mature_size_return_rate
from `{project_id}.r360_marts.mart_sizepath_daily`
group by used_size_path
order by used_size_path
