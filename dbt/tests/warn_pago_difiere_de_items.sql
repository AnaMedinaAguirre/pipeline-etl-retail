{{ config(severity='warn') }}
-- ADVERTENCIA (no detiene el pipeline): pedidos cuyo monto pagado difiere del
-- valor de productos + flete en más de 1 BRL. En Olist ocurre en una fracción
-- pequeña de pedidos (intereses por cuotas, vouchers); se monitorea su cantidad.
select order_id, valor_total_brl, monto_pagado_brl
from {{ ref('int_pedidos') }}
where cantidad_items > 0
  and monto_pagado_brl > 0
  and abs(monto_pagado_brl - valor_total_brl) > 1
