-- Dimensión basura (junk dimension): combina los atributos de pedido que sirven
-- para filtrar los tres hechos (ventas, pedidos y pagos) sin relacionar hechos
-- entre sí. Contiene TODAS las combinaciones posibles (8 estados x 4 situaciones
-- x 2 valores de reseña = 64 filas), así la clave es estable entre ejecuciones.
with situaciones as (
    select * from (values
        ('a_tiempo',          'A tiempo',             1),
        ('con_atraso',        'Con atraso',           2),
        ('sin_fecha_entrega', 'Sin fecha de entrega', 3),
        ('no_entregado',      'No entregado',         4)
    ) as s (situacion_entrega, situacion_entrega_es, orden_situacion)
),

resena as (
    select * from (values (true, 'Con reseña'), (false, 'Sin reseña'))
        as r (tiene_resena, tiene_resena_es)
)

select
    {{ dbt_utils.generate_surrogate_key(['e.order_status', 's.situacion_entrega', 'r.tiene_resena']) }}
                                    as estado_pedido_key,
    e.order_status,
    e.estado_pedido_es,
    e.orden                         as orden_estado,
    s.situacion_entrega,
    s.situacion_entrega_es,
    s.orden_situacion,
    (s.situacion_entrega = 'con_atraso')  as es_atrasado,
    (s.situacion_entrega in ('a_tiempo', 'con_atraso')) as fue_entregado,
    r.tiene_resena,
    r.tiene_resena_es
from {{ ref('estados_pedido') }} e
cross join situaciones s
cross join resena r
