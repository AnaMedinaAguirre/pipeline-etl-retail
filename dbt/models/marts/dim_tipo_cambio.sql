-- Tipo de cambio diario (una fila por fecha). En Power BI se relaciona solo con fact_ventas.
select
    {{ fecha_key('fecha') }}                as fecha_key,
    fecha,
    extract(year from fecha)::integer       as anio,
    extract(month from fecha)::integer      as mes,
    usd_brl,
    pen_usd,
    pen_brl,
    es_imputado_bcb,
    es_imputado_bcrp,
    es_imputado,
    'BCB SGS 1 (PTAX venta); BCRP PD04640PD (SBS venta)' as fuente
from {{ ref('int_tipo_cambio_diario') }}
