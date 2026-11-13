-- Pedidos tipados. Fechas de texto -> timestamp; estado normalizado.
select
    order_id,
    customer_id,
    lower(trim(order_status))                         as order_status,
    order_purchase_timestamp::timestamp               as fecha_hora_compra,
    order_purchase_timestamp::timestamp::date         as fecha_compra,
    order_approved_at::timestamp                      as fecha_hora_aprobacion,
    order_delivered_carrier_date::timestamp           as fecha_hora_entrega_transportista,
    order_delivered_customer_date::timestamp          as fecha_hora_entrega_cliente,
    order_estimated_delivery_date::timestamp::date    as fecha_entrega_estimada,
    _cargado_en
from {{ source('raw', 'olist_orders') }}
