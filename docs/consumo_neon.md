# Consumo en Neon (plan gratuito)

Seguimiento del uso real del proyecto `pipeline-etl-retail` en Neon (región `sa-east-1`,
Postgres 18) frente a los límites del plan gratuito. Las cifras **medidas** provienen de la
propia base de datos; las **proyecciones** están marcadas como tales.

## Límites del plan gratuito (consultados en neon.com/pricing, nov-2026)

| Recurso | Límite |
|---|---|
| Almacenamiento | 1 GB por proyecto |
| Cómputo | 100 CU-h por proyecto al mes |
| Transferencia de salida (egress) | 5 GB por proyecto al mes |
| Suspensión automática | tras 5 min sin actividad (siempre activa) |
| Historial (restauración) | 6 h |

## Almacenamiento

### Medición 1 · 2026-11-12, tras el run 7 (fase 3)

Datos cargados: pedidos del 2016-09-04 al 2018-01-28 (**51 939 de 99 441 pedidos, 52 %**).

| Esquema | Tamaño |
|---|---:|
| raw | 74 MB |
| marts | 52 MB |
| audit, control, referencia | < 0,2 MB |
| staging, intermediate, reporting | 0 MB (vistas) |
| **Base completa** (`pg_database_size`) | **135 MB** |

Tablas más grandes: `raw.olist_order_items` 16 MB, `raw.olist_orders` 16 MB,
`marts.fact_ventas` 16 MB, `raw.olist_order_reviews` 15 MB, `marts.fact_pedidos` 14 MB.

**Proyección con el dataset completo (estimación lineal):** unos **260 MB**, alrededor del
26 % del límite de 1 GB.

Consultas usadas:

```sql
SELECT pg_size_pretty(pg_database_size(current_database()));

SELECT n.nspname, pg_size_pretty(sum(pg_total_relation_size(c.oid)))
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'm')
GROUP BY 1 ORDER BY sum(pg_total_relation_size(c.oid)) DESC;
```

## Cómputo y egress

*Pendiente de medir en la fase 4*, con el workflow diario de GitHub Actions funcionando,
desde el panel *Usage* de la consola de Neon.

Referencia medida en local: un run diario completo (extract + load + `dbt build` con 134
tests) dura **unos 55 s**. Con la suspensión a los 5 minutos, cada run mantiene el cómputo
activo unos 6 minutos.
