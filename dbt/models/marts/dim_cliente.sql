-- Una fila por cliente real (customer_unique_id).
-- Olist genera un customer_id distinto en cada pedido; si un cliente aparece con
-- varias ciudades, se toma la de su pedido más reciente.
with ultimo as (
    select distinct on (c.customer_unique_id)
        c.customer_unique_id,
        c.ciudad,
        c.uf
    from {{ ref('stg_olist__customers') }} c
    join {{ ref('stg_olist__orders') }} o on o.customer_id = c.customer_id
    order by c.customer_unique_id, o.fecha_hora_compra desc
),

primera_compra as (
    select
        c.customer_unique_id,
        min(o.fecha_compra) as fecha_primera_compra
    from {{ ref('stg_olist__customers') }} c
    join {{ ref('stg_olist__orders') }} o on o.customer_id = c.customer_id
    group by c.customer_unique_id
)

select
    {{ dbt_utils.generate_surrogate_key(['u.customer_unique_id']) }} as cliente_key,
    u.customer_unique_id,
    u.ciudad,
    u.uf,
    e.nombre_estado,
    e.nombre_es       as nombre_estado_es,
    e.region,
    p.fecha_primera_compra
from ultimo u
join primera_compra p using (customer_unique_id)
left join {{ ref('estados_brasil') }} e on e.uf = u.uf
