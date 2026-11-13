-- ==========================================================
-- 001 · Esquemas por capa (idempotente)
-- ==========================================================
-- raw          : datos tal cual llegan de Olist / APIs de tipo de cambio
-- staging      : limpieza y tipado (vistas dbt)
-- intermediate : lógica de negocio intermedia (dbt)
-- marts        : modelo estrella (tablas dbt)
-- reporting    : vistas para Power BI (único esquema visible al rol powerbi_lector)
-- control      : watermark del simulador de llegada de datos
-- audit        : observabilidad del pipeline (etl_runs)

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS reporting;
CREATE SCHEMA IF NOT EXISTS control;
CREATE SCHEMA IF NOT EXISTS audit;

COMMENT ON SCHEMA raw          IS 'Datos crudos tal cual llegan (Olist, BCRP, BCB)';
COMMENT ON SCHEMA staging      IS 'Limpieza y tipado (dbt, vistas)';
COMMENT ON SCHEMA intermediate IS 'Transformaciones intermedias (dbt)';
COMMENT ON SCHEMA marts        IS 'Modelo estrella (dbt, tablas)';
COMMENT ON SCHEMA reporting    IS 'Vistas de consumo para Power BI';
COMMENT ON SCHEMA control      IS 'Tablas de control del simulador (watermark)';
COMMENT ON SCHEMA audit        IS 'Observabilidad del pipeline (etl_runs)';
