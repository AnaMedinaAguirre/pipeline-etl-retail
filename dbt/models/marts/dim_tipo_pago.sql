-- Medios de pago traducidos al español.
select
    {{ dbt_utils.generate_surrogate_key(['payment_type']) }} as tipo_pago_key,
    payment_type,
    tipo_pago_es
from {{ ref('tipos_pago') }}
