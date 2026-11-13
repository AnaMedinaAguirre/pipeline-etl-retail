-- Promedio mensual BRL por USD publicado por el BCRP (PN01225XM), para validación.
select
    fuente,
    serie,
    periodo,
    {{ a_numero('valor_original') }}  as valor
from {{ source('raw', 'tipo_cambio_mensual') }}
