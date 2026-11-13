-- Pagos tipados (montos en BRL). Un pedido puede pagarse con varios medios.
select
    order_id,
    payment_sequential::integer             as secuencia_pago,
    lower(trim(payment_type))               as payment_type,
    payment_installments::integer           as cuotas,
    {{ a_numero('payment_value') }}         as monto_brl
from {{ source('raw', 'olist_order_payments') }}
