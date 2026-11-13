-- Calendario completo (no solo días con ventas), con nombres en español.
with dias as (
    select generate_series(
        '{{ var("fecha_inicio_calendario") }}'::date,
        '{{ var("fecha_fin_calendario") }}'::date,
        interval '1 day'
    )::date as fecha
)

select
    {{ fecha_key('fecha') }}                                   as fecha_key,
    fecha,
    extract(year from fecha)::integer                          as anio,
    extract(quarter from fecha)::integer                       as trimestre,
    'T' || extract(quarter from fecha)::integer                as trimestre_nombre,
    extract(month from fecha)::integer                         as mes,
    (array['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio',
           'Agosto','Septiembre','Octubre','Noviembre','Diciembre'])
        [extract(month from fecha)::integer]                   as mes_nombre,
    (array['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'])
        [extract(month from fecha)::integer]                   as mes_abrev,
    to_char(fecha, 'YYYY-MM')                                  as anio_mes,
    (extract(year from fecha) * 100 + extract(month from fecha))::integer as anio_mes_num,
    date_trunc('month', fecha)::date                           as inicio_mes,
    extract(isodow from fecha)::integer                        as dia_semana,
    (array['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'])
        [extract(isodow from fecha)::integer]                  as dia_semana_nombre,
    extract(day from fecha)::integer                           as dia_mes,
    extract(week from fecha)::integer                          as semana_iso,
    extract(isodow from fecha) in (6, 7)                       as es_fin_de_semana
from dias
