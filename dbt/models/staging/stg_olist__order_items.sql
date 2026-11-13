-- Ítems de pedido tipados (montos en BRL).
select
    order_id,
    order_item_id::integer                  as order_item_id,
    product_id,
    seller_id,
    shipping_limit_date::timestamp          as fecha_limite_envio,
    {{ a_numero('price') }}                 as precio_brl,
    {{ a_numero('freight_value') }}         as flete_brl
from {{ source('raw', 'olist_order_items') }}
