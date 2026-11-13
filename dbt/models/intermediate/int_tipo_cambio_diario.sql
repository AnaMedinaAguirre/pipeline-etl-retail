-- Tipo de cambio para TODOS los días calendario (incluidos fines de semana y feriados).
--
-- Las APIs solo publican días hábiles y los feriados de Brasil y Perú no coinciden,
-- así que cada serie se rellena por separado con su último valor publicado
-- ("forward fill"). Cada valor rellenado queda marcado como imputado.
--
--   usd_brl : BRL por 1 USD  (BCB, PTAX venta)
--   pen_usd : PEN por 1 USD  (BCRP, TC SBS venta)
--   pen_brl : PEN por 1 BRL  = pen_usd / usd_brl  (cruce vía USD)

with limites as (
    select
        (select min(fecha) from {{ ref('stg_fx__diario') }})              as desde,
        greatest(
            (select max(fecha) from {{ ref('stg_fx__diario') }}),
            (select max(fecha_compra) from {{ ref('stg_olist__orders') }})
        )                                                                  as hasta
),

calendario as (
    select generate_series(desde, hasta, interval '1 day')::date as fecha
    from limites
),

series as (
    select
        c.fecha,
        bcb.valor  as usd_brl_publicado,
        bcrp.valor as pen_usd_publicado
    from calendario c
    left join {{ ref('stg_fx__diario') }} bcb
        on bcb.fecha = c.fecha and bcb.serie = 'SGS1'
    left join {{ ref('stg_fx__diario') }} bcrp
        on bcrp.fecha = c.fecha and bcrp.serie = 'PD04640PD'
),

-- Truco de "grupos": el contador de valores no nulos solo aumenta cuando hay dato,
-- así todos los días sin dato quedan en el grupo del último día publicado.
grupos as (
    select
        *,
        count(usd_brl_publicado) over (order by fecha) as grupo_bcb,
        count(pen_usd_publicado) over (order by fecha) as grupo_bcrp
    from series
),

rellenado as (
    select
        fecha,
        max(usd_brl_publicado) over (partition by grupo_bcb)  as usd_brl,
        max(pen_usd_publicado) over (partition by grupo_bcrp) as pen_usd,
        usd_brl_publicado is null                             as es_imputado_bcb,
        pen_usd_publicado is null                             as es_imputado_bcrp
    from grupos
)

select
    fecha,
    usd_brl,
    pen_usd,
    round(pen_usd / usd_brl, 6)              as pen_brl,
    es_imputado_bcb,
    es_imputado_bcrp,
    (es_imputado_bcb or es_imputado_bcrp)    as es_imputado
from rellenado
-- Solo días con ambas series disponibles (descarta el arranque si una serie empieza después)
where usd_brl is not null and pen_usd is not null
