{{
    config(
        materialized='incremental',
        unique_key='order_id',
        incremental_strategy='delete+insert',
        on_schema_change='fail'
    )
}}
-- Hecho de pedidos (accumulating snapshot). Grano: un pedido.
-- Métricas de entrega y de reseña, que no pueden ir en fact_ventas sin duplicarse
-- en los pedidos con varios ítems. Incluye pedidos sin ítems (cancelados/no disponibles).

with pedidos as (
    select *
    from {{ ref('int_pedidos') }}
    {% if is_incremental() %}
    where _cargado_en > (select coalesce(max(_cargado_en), '1900-01-01'::timestamptz) from {{ this }})
    {% endif %}
)

select
    p.order_id,
    {{ fecha_key('p.fecha_compra') }}                                       as fecha_key,
    {{ dbt_utils.generate_surrogate_key(['c.customer_unique_id']) }}        as cliente_key,
    {{ dbt_utils.generate_surrogate_key(['p.order_status', 'p.situacion_entrega', 'p.tiene_resena']) }}
                                                                            as estado_pedido_key,
    p.fecha_hora_compra,
    p.fecha_hora_aprobacion,
    p.fecha_hora_entrega_transportista,
    p.fecha_entrega_cliente,
    p.fecha_entrega_estimada,
    p.dias_entrega_real,
    p.dias_entrega_estimado,
    p.dias_diferencia_vs_estimado,
    p.nota_resena,
    p.cantidad_items,
    p.cantidad_vendedores,
    p.valor_productos_brl,
    p.valor_flete_brl,
    p.valor_total_brl,
    round(p.valor_total_brl / tc.usd_brl, 2)                               as valor_total_usd,
    round(p.valor_total_brl * tc.pen_brl, 2)                               as valor_total_pen,
    p.monto_pagado_brl,
    p._cargado_en
from pedidos p
join {{ ref('stg_olist__customers') }} c         on c.customer_id = p.customer_id
left join {{ ref('int_tipo_cambio_diario') }} tc on tc.fecha = p.fecha_compra
