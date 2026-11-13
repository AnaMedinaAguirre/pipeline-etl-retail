-- Vendedores con ubicación (UF, estado y región).
select
    {{ dbt_utils.generate_surrogate_key(['s.seller_id']) }} as vendedor_key,
    s.seller_id,
    s.ciudad,
    s.uf,
    e.nombre_estado,
    e.nombre_es       as nombre_estado_es,
    e.region
from {{ ref('stg_olist__sellers') }} s
left join {{ ref('estados_brasil') }} e on e.uf = s.uf
