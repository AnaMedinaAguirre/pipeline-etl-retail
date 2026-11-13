-- Los tres hechos son incrementales e independientes; este test verifica que
-- sigan siendo consistentes entre sí (no se pueden relacionar en Power BI, así que
-- la consistencia se garantiza aquí):
--   1. ventas de fact_ventas  = valor de ítems de fact_pedidos
--   2. pagos de fact_pagos    = monto pagado de fact_pedidos
--   3. todo pedido de fact_ventas y fact_pagos existe en fact_pedidos
with totales as (
    select
        (select coalesce(sum(total_brl), 0) from {{ ref('fact_ventas') }})            as ventas_hecho,
        (select coalesce(sum(valor_total_brl), 0) from {{ ref('fact_pedidos') }})     as ventas_pedidos,
        (select coalesce(sum(monto_brl), 0) from {{ ref('fact_pagos') }})             as pagos_hecho,
        (select coalesce(sum(monto_pagado_brl), 0) from {{ ref('fact_pedidos') }})    as pagos_pedidos,
        (select count(*) from {{ ref('fact_ventas') }} v
          where not exists (select 1 from {{ ref('fact_pedidos') }} p where p.order_id = v.order_id)
        ) as ventas_huerfanas,
        (select count(*) from {{ ref('fact_pagos') }} g
          where not exists (select 1 from {{ ref('fact_pedidos') }} p where p.order_id = g.order_id)
        ) as pagos_huerfanos
)

select *
from totales
where ventas_hecho <> ventas_pedidos
   or pagos_hecho <> pagos_pedidos
   or ventas_huerfanas > 0
   or pagos_huerfanos > 0
