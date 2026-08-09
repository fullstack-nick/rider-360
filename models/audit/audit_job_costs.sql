select
  current_timestamp() as captured_at,
  job_id,
  creation_time,
  start_time,
  end_time,
  job_type,
  statement_type,
  state,
  cache_hit,
  total_bytes_processed,
  total_bytes_billed,
  total_slot_ms,
  error_result.reason as error_reason,
  destination_table.project_id as destination_project_id,
  destination_table.dataset_id as destination_dataset_id,
  destination_table.table_id as destination_table_id
from `region-EU`.INFORMATION_SCHEMA.JOBS_BY_USER
where creation_time >= timestamp_sub(current_timestamp(), interval 30 day)
  and coalesce(statement_type, 'UNKNOWN') != 'SCRIPT'
  and (
    regexp_contains(coalesce(query, ''), r'Rider 360 dbt:')
    or exists (
      select 1
      from unnest(labels) as label
      where label.key = 'app' and label.value = 'rider-360'
    )
  )
