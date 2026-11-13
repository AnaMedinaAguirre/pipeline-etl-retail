-- Un registro por pedido con métricas de entrega, reseña y totales.
-- Base de fact_pedidos y fuente de los atributos de dim_estado_pedido.

with resenas as (
    -- Olist tiene pedidos con varias reseñas: se toma la más reciente
    select distinct on (order_id)
        order_id,
        nota
    from {{ ref('stg_olist__order_reviews') }}
    order by order_id, fecha_hora_respuesta desc nulls last, fecha_hora_creacion desc
),

items as (
    select
        order_id,
        count(*)                   as cantidad_items,
        count(distinct seller_id)  as cantidad_vendedores,
        sum(precio_brl)            as valor_productos_brl,
        sum(flete_brl)             as valor_flete_brl
    from {{ ref('stg_olist__order_items') }}
    group by order_id
),

pagos as (
    select
        order_id,
        sum(monto_brl) as monto_pagado_brl
    from {{ ref('stg_olist__order_payments') }}
    group by order_id
)

select
    o.order_id,
    o.customer_id,
    o.order_status,
    o.fecha_hora_compra,
    o.fecha_compra,
    o.fecha_hora_aprobacion,
    o.fecha_hora_entrega_transportista,
    o.fecha_hora_entrega_cliente,
    o.fecha_hora_entrega_cliente::date                       as fecha_entrega_cliente,
    o.fecha_entrega_estimada,

    -- Situación de entrega (atributo de la dimensión basura)
    case
        when o.fecha_hora_entrega_cliente is not null
             and o.fecha_hora_entrega_cliente::date <= o.fecha_entrega_estimada then 'a_tiempo'
        when o.fecha_hora_entrega_cliente is not null                          then 'con_atraso'
        when o.order_status = 'delivered'                                      then 'sin_fecha_entrega'
        else 'no_entregado'
    end                                                       as situacion_entrega,

    -- Días calendario (enteros)
    o.fecha_hora_entrega_cliente::date - o.fecha_compra       as dias_entrega_real,
    o.fecha_entrega_estimada - o.fecha_compra                 as dias_entrega_estimado,
    o.fecha_hora_entrega_cliente::date - o.fecha_entrega_estimada as dias_diferencia_vs_estimado,

    r.nota                                                    as nota_resena,
    (r.order_id is not null)                                  as tiene_resena,

    coalesce(i.cantidad_items, 0)                             as cantidad_items,
    coalesce(i.cantidad_vendedores, 0)                        as cantidad_vendedores,
    coalesce(i.valor_productos_brl, 0)                        as valor_productos_brl,
    coalesce(i.valor_flete_brl, 0)                            as valor_flete_brl,
    coalesce(i.valor_productos_brl, 0) + coalesce(i.valor_flete_brl, 0) as valor_total_brl,
    coalesce(p.monto_pagado_brl, 0)                           as monto_pagado_brl,

    o._cargado_en
from {{ ref('stg_olist__orders') }} o
left join resenas r on r.order_id = o.order_id
left join items   i on i.order_id = o.order_id
left join pagos   p on p.order_id = o.order_id
