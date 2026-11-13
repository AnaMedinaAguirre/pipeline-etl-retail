{{
    config(
        materialized='incremental',
        unique_key=['order_id', 'secuencia_pago'],
        incremental_strategy='delete+insert',
        on_schema_change='fail'
    )
}}
-- Hecho de pagos. Grano: un pago de un pedido (un pedido puede tener varios).
-- Se conecta a las dimensiones, NO a fact_pedidos (evita relaciones hecho-hecho en Power BI).

with pedidos as (
    select *
    from {{ ref('int_pedidos') }}
    {% if is_incremental() %}
    where _cargado_en > (select coalesce(max(_cargado_en), '1900-01-01'::timestamptz) from {{ this }})
    {% endif %}
)

select
    pg.order_id,
    pg.secuencia_pago,
    {{ fecha_key('p.fecha_compra') }}                                       as fecha_key,
    {{ dbt_utils.generate_surrogate_key(['c.customer_unique_id']) }}        as cliente_key,
    {{ dbt_utils.generate_surrogate_key(['pg.payment_type']) }}             as tipo_pago_key,
    {{ dbt_utils.generate_surrogate_key(['p.order_status', 'p.situacion_entrega', 'p.tiene_resena']) }}
                                                                            as estado_pedido_key,
    pg.cuotas,
    pg.monto_brl,
    round(pg.monto_brl / tc.usd_brl, 2)                                     as monto_usd,
    round(pg.monto_brl * tc.pen_brl, 2)                                     as monto_pen,
    p._cargado_en
from {{ ref('stg_olist__order_payments') }} pg
join pedidos p                                   on p.order_id = pg.order_id
join {{ ref('stg_olist__customers') }} c         on c.customer_id = p.customer_id
left join {{ ref('int_tipo_cambio_diario') }} tc on tc.fecha = p.fecha_compra
