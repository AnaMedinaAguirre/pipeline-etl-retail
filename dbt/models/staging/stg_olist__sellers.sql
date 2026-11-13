-- Vendedores con ciudad estandarizada.
select
    seller_id,
    seller_zip_code_prefix                                   as codigo_postal_prefijo,
    initcap(regexp_replace(trim(seller_city), '\s+', ' ', 'g'))  as ciudad,
    upper(trim(seller_state))                                as uf
from {{ source('raw', 'olist_sellers') }}
