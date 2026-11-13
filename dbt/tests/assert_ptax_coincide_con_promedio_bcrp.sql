-- Validación cruzada de fuentes: el promedio mensual de la PTAX diaria del BCB
-- (solo días publicados, sin imputados) no debe diferir del promedio mensual BRL/USD
-- que publica el BCRP (PN01225XM) en más de la tolerancia configurada.
-- Solo se evalúan meses completos dentro del rango cargado.
with ptax_mensual as (
    select
        date_trunc('month', fecha)::date as periodo,
        avg(valor)                       as promedio_bcb,
        count(*)                         as dias_publicados
    from {{ ref('stg_fx__diario') }}
    where serie = 'SGS1' and valor is not null
    group by 1
),

meses_completos as (
    -- un mes está completo si hay datos hasta su último día hábil (>= día 25)
    select periodo
    from ptax_mensual p
    where exists (
        select 1 from {{ ref('stg_fx__diario') }} d
        where d.serie = 'SGS1'
          and date_trunc('month', d.fecha)::date = p.periodo
          and extract(day from d.fecha) >= 25
    )
      and exists (
        select 1 from {{ ref('stg_fx__diario') }} d
        where d.serie = 'SGS1'
          and date_trunc('month', d.fecha)::date = p.periodo
          and extract(day from d.fecha) <= 5
    )
)

select
    p.periodo,
    round(p.promedio_bcb, 4)                         as promedio_bcb,
    round(m.valor, 4)                                as promedio_bcrp,
    round(abs(p.promedio_bcb - m.valor) / m.valor, 4) as diferencia_relativa
from ptax_mensual p
join meses_completos using (periodo)
join {{ ref('stg_fx__mensual') }} m
  on m.periodo = p.periodo and m.serie = 'PN01225XM'
where m.valor is not null
  and abs(p.promedio_bcb - m.valor) / m.valor > {{ var('tolerancia_validacion_fx') }}
