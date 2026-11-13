{#
  Convierte un texto de raw a numeric solo si tiene formato numérico válido;
  si no (p. ej. 'n.d.' o vacío), devuelve NULL en lugar de fallar.
#}
{% macro a_numero(columna) -%}
    case
        when trim({{ columna }}) ~ '^-?[0-9]+(\.[0-9]+)?$' then trim({{ columna }})::numeric
    end
{%- endmacro %}

{#
  Clave entera AAAAMMDD a partir de una fecha (para dim_fecha y los hechos).
#}
{% macro fecha_key(columna) -%}
    (to_char({{ columna }}, 'YYYYMMDD'))::integer
{%- endmacro %}
