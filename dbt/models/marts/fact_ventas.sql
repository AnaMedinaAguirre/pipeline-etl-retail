{{
    config(
        materialized='incremental',
        unique_key=['order_id', 'order_item_id'],
        incremental_strategy='delete+insert',
        on_schema_change='fail'
    )
}}
-- Hecho de ventas. Grano: un ítem de pedido.
-- Montos en BRL (fuente de verdad) y equivalentes referenciales en USD y PEN al
-- tipo de cambio del día de compra.
--
-- Incremental: en cada ejecución solo se procesan los pedidos cargados en raw
-- después de la última carga del hecho (_cargado_en). Si un lote se reprocesa,
-- sus filas se reemplazan (delete+insert por clave), sin duplicar.

with pedidos as (
    select *
    from {{ ref('int_pedidos') }}
    {% if is_incremental() %}
    where _cargado_en > (select coalesce(max(_cargado_en), '1900-01-01'::timestamptz) from {{ this }})
    {% endif %}
)

select
    i.order_id,
    i.order_item_id,
    {{ fecha_key('p.fecha_compra') }}                                       as fecha_key,
    {{ dbt_utils.generate_surrogate_key(['c.customer_unique_id']) }}        as cliente_key,
    {{ dbt_utils.generate_surrogate_key(['i.product_id']) }}                as producto_key,
    {{ dbt_utils.generate_surrogate_key(['i.seller_id']) }}                 as vendedor_key,
    {{ dbt_utils.generate_surrogate_key(['p.order_status', 'p.situacion_entrega', 'p.tiene_resena']) }}
                                                                            as estado_pedido_key,
    i.precio_brl,
    i.flete_brl,
    i.precio_brl + i.flete_brl                                              as total_brl,
    round(i.precio_brl / tc.usd_brl, 2)                                     as precio_usd,
    round((i.precio_brl + i.flete_brl) / tc.usd_brl, 2)                     as total_usd,
    round(i.precio_brl * tc.pen_brl, 2)                                     as precio_pen,
    round((i.precio_brl + i.flete_brl) * tc.pen_brl, 2)                     as total_pen,
    p._cargado_en
from {{ ref('stg_olist__order_items') }} i
join pedidos p                                  on p.order_id = i.order_id
join {{ ref('stg_olist__customers') }} c        on c.customer_id = p.customer_id
left join {{ ref('int_tipo_cambio_diario') }} tc on tc.fecha = p.fecha_compra
