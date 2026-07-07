{% macro safe_cast_date(column, format=None) %}
    {#
      Cast a string column to DATE, returning NULL on parse failure.
      DuckDB supports TRY_CAST natively.
    #}
    TRY_CAST({{ column }} AS DATE)
{% endmacro %}
