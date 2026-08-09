{% macro event_param_string(param_name) -%}
  (select ep.value.string_value from unnest(event_params) ep where ep.key = '{{ param_name }}' limit 1)
{%- endmacro %}

{% macro event_param_int(param_name) -%}
  (select ep.value.int_value from unnest(event_params) ep where ep.key = '{{ param_name }}' limit 1)
{%- endmacro %}

{% macro event_param_numeric(param_name) -%}
  coalesce(
    cast((select ep.value.double_value from unnest(event_params) ep where ep.key = '{{ param_name }}' limit 1) as numeric),
    cast((select ep.value.int_value from unnest(event_params) ep where ep.key = '{{ param_name }}' limit 1) as numeric)
  )
{%- endmacro %}
