{% set model = ref('silver_payments') %}
-- First build has a NULL baseline and cannot establish stability yet.
with current_volume as (select count(*) as current_count from {{ model }})
select previous_count, current_count
from {{ model.database }}.{{ model.schema }}._volume_baseline_silver_payments
cross join current_volume
where previous_count is not null
  and abs(current_count - previous_count) > previous_count * {{ var('volume_tolerance', 0.20) }}
