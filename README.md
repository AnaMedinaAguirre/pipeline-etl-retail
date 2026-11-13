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

`neon.ts` y `package.json` son la configuración del CLI de Neon (`neon deploy`) y no forman
parte del pipeline.

## Atribución del dataset

*Brazilian E-Commerce Public Dataset by Olist*, publicado por Olist en Kaggle bajo licencia
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). Los datos no se
redistribuyen en este repositorio: se descargan en cada ejecución mediante la API de Kaggle.
