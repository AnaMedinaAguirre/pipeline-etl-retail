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

### Configuración del cómputo

- Autoscaling limitado a **0,25 – 1 CU** (el valor por defecto era 0,25 – 2 CU). Se cambió el
  2026-11-13 con `neon api … -X PATCH` para acotar el consumo; este volumen de datos no
  necesita más de 1 CU.
- Suspensión automática: la del plan gratuito (5 min sin actividad).

### Línea base · 2026-11-13 05:15 UTC (antes de ejecutar en GitHub Actions)

Valores del periodo de facturación actual (desde 2026-11-13T02:25Z), leídos con
`neon api /projects/<id>`. Incluyen el desarrollo local de las fases 1-3 posteriores a esa hora.

| Métrica (API de Neon) | Valor |
|---|---:|
| `active_time_seconds` (tiempo con el cómputo encendido) | 3 100 s |
| `compute_time_seconds` | 838 s |
| `data_transfer_bytes` (egress) | 474 864 B (≈ 0,45 MB) |

### Medición 1 · 2026-11-13 06:00 UTC, tras el primer run en GitHub Actions (cota superior)

Run 8 (`workflow_dispatch`): ventana 2018-01-29 → 2018-02-04, 138 tests OK, 73 s de
pipeline (2 min 40 s el workflow completo, incluida la publicación de dbt docs).

| Métrica | Línea base | Medición | Diferencia |
|---|---:|---:|---:|
| `active_time_seconds` | 3 100 | 4 268 | +1 168 s (19,5 min) |
| `compute_time_seconds` | 838 | 1 142 | +304 s |
| `data_transfer_bytes` | 474 864 | 537 206 | +62 342 B (≈ 61 KB) |

**Salvedad:** la diferencia incluye, además del run 8, pruebas locales contra la misma base
(pytest con tests de integración a las 05:43 UTC) y la consulta de esta medición. Es una
**cota superior** del costo de un run, no el costo exacto.

`compute_time_seconds` coincide aproximadamente con el tiempo activo × 0,25 CU
(1 168 s × 0,25 ≈ 292), así que se interpreta como CU-segundos: **≈ 0,08 CU-h** en este
intervalo. Aunque cada run diario costara eso, 31 runs al mes serían unas 2,6 CU-h, alrededor
del **2,6 % de las 100 CU-h** del plan gratuito. El egress del pipeline es mínimo (≈ 61 KB),
porque las transformaciones corren dentro de la base.

### Conclusión (punto cerrado)

Se adopta la **cota superior** como estimación de consumo del proyecto; no se hará una
medición aislada por run.

| Recurso | Estimación mensual (31 runs) | Límite gratuito | Uso |
|---|---:|---:|---:|
| Cómputo | ≤ 2,6 CU-h | 100 CU-h | ≤ 2,6 % |
| Almacenamiento (dataset completo, proyección) | ≈ 260 MB | 1 GB | ≈ 26 % |
| Egress del pipeline | < 2 MB | 5 GB | < 0,1 % |

Para una medición aislada habría que tener en cuenta dos cosas:
- Los contadores de la API (`active_time_seconds`, `compute_time_seconds`) se actualizan con
  retraso: una lectura tomada minutos después de un run todavía no lo incluye.
- La API de consumo por hora (`/consumption_history`) no está disponible en el plan gratuito.

El historial de operaciones (`neon api /projects/<id>/operations`) sí permite comprobar cuándo
se encendió y suspendió el cómputo. Por ejemplo, el run 8 lo mantuvo activo de 05:48:51 a
05:56:00 UTC, unos 7 minutos (≈ 0,03 CU-h a 0,25 CU).

El refresco manual de Power BI se sumará a estos valores (se estimará en la fase 5).

Referencia medida en local: un run diario completo (extract + load + `dbt build` con 134
tests) dura **unos 55 s**. Con la suspensión a los 5 minutos, cada run mantiene el cómputo
activo unos 6 minutos.
