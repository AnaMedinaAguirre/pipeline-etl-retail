-- Tipos de cambio diarios. Valores no numéricos del BCRP ('n.d.') quedan en NULL
-- y se rellenan en intermediate con el último valor disponible.
select
    fuente,
    serie,
    fecha,
    {{ a_numero('valor_original') }}  as valor
from {{ source('raw', 'tipo_cambio_diario') }}
