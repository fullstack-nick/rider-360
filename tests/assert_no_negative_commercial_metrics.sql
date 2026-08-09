select * from {{ ref('mart_executive_daily') }}
where sessions < 0 or orders < 0 or revenue_eur < 0 or marketing_spend_eur < 0
