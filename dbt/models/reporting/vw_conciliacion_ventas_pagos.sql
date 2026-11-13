-- Conciliación mensual entre "ventas" (precio + flete de los ítems) y "total pagado"
-- (pagos registrados). Explica la diferencia por componentes para que el dashboard
-- no confunda ambas cifras:
--
--   total_pagado_brl = ventas_brl
--                    + pagado_pedidos_sin_items_brl     (pedidos cancelados/no disponibles
--                                                         que no llegaron a tener ítems)
--                    + diferencia_cuotas_brl            (pedidos con ítems cuyo pago difiere
--                                                         en más de 1 BRL; neto)
--                    + diferencia_redondeo_brl          (diferencias de hasta 1 BRL)
select
    d.anio_mes,
    d.inicio_mes,
    count(*) filter (where p.cantidad_items > 0)                         as pedidos_con_items,
    count(*) filter (where p.cantidad_items = 0 and p.monto_pagado_brl > 0) as pedidos_sin_items_con_pago,
    sum(p.valor_total_brl)                                               as ventas_brl,
    sum(p.monto_pagado_brl) filter (where p.cantidad_items = 0)          as pagado_pedidos_sin_items_brl,
    coalesce(sum(p.monto_pagado_brl - p.valor_total_brl) filter (
        where p.cantidad_items > 0 and abs(p.monto_pagado_brl - p.valor_total_brl) > 1
    ), 0)                                                                as diferencia_cuotas_brl,
    coalesce(sum(p.monto_pagado_brl - p.valor_total_brl) filter (
        where p.cantidad_items > 0 and abs(p.monto_pagado_brl - p.valor_total_brl) <= 1
    ), 0)                                                                as diferencia_redondeo_brl,
    sum(p.monto_pagado_brl)                                              as total_pagado_brl
from {{ ref('fact_pedidos') }} p
join {{ ref('dim_fecha') }} d using (fecha_key)
group by d.anio_mes, d.inicio_mes
