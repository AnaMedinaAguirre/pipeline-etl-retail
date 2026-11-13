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
