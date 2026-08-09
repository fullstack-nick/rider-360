with deliveries as (
  select
    source_name,
    partition_date,
    expected_at,
    received_at,
    loaded_at,
    row_count,
    timestamp_diff(received_at, expected_at, minute) as arrival_lag_minutes
  from {{ source('raw', 'source_delivery_log') }}
), latest_partitions as (
  select source_name, max(partition_date) as data_through
  from deliveries
  group by 1
)
select
  current_timestamp() as observed_at,
  d.source_name,
  l.data_through,
  max(d.received_at) as latest_received_at,
  max(d.loaded_at) as latest_source_reported_loaded_at,
  sum(d.row_count) as latest_partition_rows,
  max(d.arrival_lag_minutes) as maximum_arrival_lag_minutes,
  countif(d.arrival_lag_minutes > 30) as deliveries_over_30_minutes_late,
  if(countif(d.arrival_lag_minutes > 30) = 0, 'pass', 'warning') as arrival_status
from deliveries d
join latest_partitions l
  on d.source_name = l.source_name
  and d.partition_date = l.data_through
group by 2, 3
