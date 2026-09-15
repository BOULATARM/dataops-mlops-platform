{% macro capture_previous_volume() %}
  {% set previous = adapter.get_relation(database=this.database, schema=this.schema, identifier=this.identifier) if execute else none %}
  create or replace table {{ this.database }}.{{ this.schema }}.{{ adapter.quote('_volume_baseline_' ~ this.identifier) }} as
  {% if previous is not none %}
    select count(*)::bigint as previous_count, current_timestamp as captured_at from {{ previous }}
  {% else %}
    select null::bigint as previous_count, current_timestamp as captured_at
  {% endif %}
{% endmacro %}
