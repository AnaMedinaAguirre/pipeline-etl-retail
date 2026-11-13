{#
  Por defecto dbt antepone el esquema del target al esquema personalizado
  (p. ej. "marts_staging"). Aquí se usa el esquema personalizado tal cual,
  para que los modelos queden en staging / intermediate / marts / referencia.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
