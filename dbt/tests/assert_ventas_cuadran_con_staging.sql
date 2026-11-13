-- Reconciliación: fact_ventas debe tener exactamente los mismos ítems y el mismo
-- monto total en BRL que staging. Devuelve una fila (= falla) si no cuadra.
with hecho as (
    select count(*) as filas, sum(precio_brl) as precio, sum(flete_brl) as flete
    from {{ ref('fact_ventas') }}
),

origen as (
    select count(*) as filas, sum(precio_brl) as precio, sum(flete_brl) as flete
    from {{ ref('stg_olist__order_items') }}
)

select h.*, o.filas as filas_origen, o.precio as precio_origen, o.flete as flete_origen
from hecho h cross join origen o
where h.filas <> o.filas or h.precio <> o.precio or h.flete <> o.flete
