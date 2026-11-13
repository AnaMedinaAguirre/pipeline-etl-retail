# Pipeline ETL automatizado de ventas retail (Olist)

> 🚧 Proyecto en construcción (fase 1: setup). La documentación completa, el diagrama de
> arquitectura, el modelo estrella y los resultados se publicarán al terminar las fases.

Pipeline ELT con **Python + dbt + PostgreSQL (Neon) + GitHub Actions + Power BI** sobre el
dataset público *Brazilian E-Commerce Public Dataset by Olist*. Los equivalentes en USD y PEN
se calculan con tipos de cambio oficiales del BCB (Brasil) y del BCRP (Perú).

## Setup local (Windows / PowerShell)

```powershell
# 1. Entorno Python 3.12
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pip install -e .

# 2. Credenciales (nunca se suben al repo)
Copy-Item .env.example .env      # completa KAGGLE_USERNAME y KAGGLE_KEY
neon deploy                      # agrega DATABASE_URL_UNPOOLED a .env

# 3. Base de datos
python -m etl.setup_db           # esquemas, control y auditoría (idempotente)
python -m etl.crear_rol_powerbi  # rol de solo lectura para Power BI
python -m etl.probar_conexion    # verificación
```

## Ejecutar el pipeline

```powershell
python -m etl.main --dry-run   # muestra la ventana y las filas del próximo lote, sin escribir
python -m etl.main             # siguiente lote según el watermark (BATCH_DAYS días)
python -m etl.main --dias 30   # este run recibe 30 días
python -m pytest               # tests unitarios + integración (si hay DATABASE_URL)
```

**Simulador de llegada de datos:** Olist es histórico (2016-09-04 → 2018-10-17). La primera
ejecución carga hasta `FECHA_CARGA_INICIAL`; cada ejecución siguiente "recibe" los
`BATCH_DAYS` días siguientes de pedidos, controlados por `control.watermark`. La carga es
idempotente (borrar por clave + insertar, en una sola transacción) y el watermark solo
avanza si el run termina bien.

## Transformación y calidad de datos (dbt)

```powershell
python -m etl.dbt_cli build                    # seeds + modelos + tests (lo que corre el pipeline)
python -m etl.dbt_cli build --select marts     # solo la capa marts y sus tests
python -m etl.dbt_cli build --full-refresh     # reconstruye los hechos incrementales desde cero
```

`etl.dbt_cli` arma las credenciales de dbt a partir de `DATABASE_URL`, así `dbt/profiles.yml`
no contiene secretos.

| Capa | Esquema | Materialización | Contenido |
|---|---|---|---|
| staging | `staging` | vistas | tipado, nulos, deduplicación de reseñas, ciudades estandarizadas |
| intermediate | `intermediate` | vistas | tipo de cambio diario con relleno de fines de semana y feriados; métricas por pedido |
| marts | `marts` | tablas (hechos incrementales) | `fact_ventas`, `fact_pedidos`, `fact_pagos`, `dim_fecha`, `dim_cliente`, `dim_producto`, `dim_vendedor`, `dim_tipo_pago`, `dim_estado_pedido`, `dim_tipo_cambio` |
| seeds | `referencia` | tablas | categorías PT/EN/ES con grupo, estados de Brasil y región, medios de pago, estados de pedido |

**Tests de calidad (134):** claves únicas y no nulas, relaciones entre hechos y dimensiones,
rangos de montos, fechas y notas, categorías traducidas, reconciliación de `fact_ventas` con
staging y validación cruzada de la PTAX diaria (BCB) contra el promedio mensual del BCRP.
**Si un test falla, `dbt build` falla, el run queda `fallido` y el watermark no avanza.** El
test `warn_pago_difiere_de_items` es solo una advertencia: monitorea los pedidos cuyo pago
difiere de productos + flete en más de 1 BRL (intereses de cuotas, vouchers).

### Característica del dataset: pagos que no coinciden con productos + flete

Medición del 2026-11-12, con los pedidos cargados hasta el 2018-01-28 que tienen ítems y pagos:

| Métrica | Valor |
|---|---:|
| Pedidos evaluados | 51 352 |
| Pedidos cuyo pago difiere de productos + flete en más de 1 BRL | **165 (0,32 %)** |
| Diferencia absoluta promedio / máxima | 13,67 BRL / 182,81 BRL |
| Pago **mayor** que productos + flete | 163 |
| Pago **menor** que productos + flete | 2 |

| Causa probable (pedidos con diferencia) | Pedidos | Diferencia promedio | % promedio sobre el pedido |
|---|---:|---:|---:|
| Pago mayor, tarjeta de crédito en cuotas | 161 | 13,59 BRL | 11,25 % |
| Pago mayor, sin cuotas | 2 | 1,44 BRL | 4,20 % |
| Pago menor, sin voucher | 2 | 32,69 BRL | 21,71 % |

**Interpretación:** casi todas las diferencias (161 de 165) son pagos con tarjeta en cuotas que
superan el valor del pedido, lo que es coherente con **intereses de financiamiento**. Pagar en
cuotas por sí solo no genera diferencia: el 52,8 % de los pedidos que sí cuadran también se
pagaron en cuotas, porque en Brasil es habitual el "parcelado sem juros" (cuotas sin interés).
Los vouchers no explican ninguna diferencia en este periodo. El dataset no documenta la causa,
así que se trata como una **característica de los datos y no como un error**: el test
`warn_pago_difiere_de_items` la monitorea como advertencia, y los ingresos del modelo se
calculan con precio + flete (`fact_ventas`), no con el monto pagado.

### Evidencia: un test fallido detiene el pipeline

En el **run 6** (`origen = 'prueba_calidad'`) se inyectó a propósito en `raw.olist_products`
un producto con una categoría sin traducción. `dbt build` falló en el test de relación con el
seed `categorias_es`, el run terminó `fallido` con código de salida 1 y el watermark se quedó
en 2018-01-21. Tras eliminar el dato, el **run 7** reprocesó la misma ventana
(2018-01-22 → 2018-01-28) con 134 tests OK y 0 fallidos.

### Evidencia de idempotencia

Para comprobar que reprocesar un lote no duplica datos, se retrocedió el watermark a
2017-12-31 y se volvió a cargar la semana 2018-01-01 → 2018-01-07, ya cargada por el run 2.
Ese reproceso es el **run 3** y en `audit.etl_runs` está marcado con
`origen = 'prueba_idempotencia'` (en `reporting.vw_etl_runs`: `es_prueba = true`), para no
confundirlo con una carga normal duplicada.

| Tabla raw | Filas antes del reproceso | Filas reemplazadas en el run 3 | Filas después |
|---|---:|---:|---:|
| olist_orders | 46 813 | 1 383 | 46 813 |
| olist_order_items | 52 795 | 1 561 | 52 795 |
| olist_order_payments | 49 318 | 1 447 | 49 318 |
| olist_order_reviews | 46 745 | 1 375 | 46 745 |
| olist_customers | 46 813 | 1 383 | 46 813 |
| olist_products | 17 884 | 1 083 | 17 884 |
| olist_sellers | 1 840 | 475 | 1 840 |
| tipo_cambio_diario | 704 | 28 (upsert) | 704 |

En todas las tablas el número de filas coincide con el de claves únicas. La misma propiedad
se verifica automáticamente en `tests/integracion/test_idempotencia_carga.py`.

`neon.ts` y `package.json` son la configuración del CLI de Neon (`neon deploy`) y no forman
parte del pipeline.

## Atribución del dataset

*Brazilian E-Commerce Public Dataset by Olist*, publicado por Olist en Kaggle bajo licencia
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). Los datos no se
redistribuyen en este repositorio: se descargan en cada ejecución mediante la API de Kaggle.
