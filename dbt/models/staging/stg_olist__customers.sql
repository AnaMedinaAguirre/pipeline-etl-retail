-- Clientes por pedido. Ciudad estandarizada (espacios y mayúsculas), UF en mayúsculas.
select
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix                                 as codigo_postal_prefijo,
    initcap(regexp_replace(trim(customer_city), '\s+', ' ', 'g'))  as ciudad,
    upper(trim(customer_state))                              as uf
from {{ source('raw', 'olist_customers') }}
