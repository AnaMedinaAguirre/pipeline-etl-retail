-- ==========================================================
-- 003 · Vistas base de reporting (idempotente)
-- Las vistas del modelo estrella se agregan en la fase 5 (dbt).
-- ==========================================================

-- Vista técnica para verificar la conexión desde Power BI.
-- No contiene datos de negocio: solo metadatos reales del servidor.
CREATE OR REPLACE VIEW reporting.vw_prueba_conexion AS
SELECT
    current_database()                     AS base_de_datos,
    current_user                           AS usuario,
    split_part(version(), ' ', 2)          AS version_postgres,
    now() AT TIME ZONE 'America/Lima'      AS hora_servidor_lima;

-- reporting.vw_etl_runs se define en 005_etl_runs_pruebas.sql
-- (necesita la columna `nota`, que se agrega allí).

CREATE OR REPLACE VIEW reporting.vw_etl_run_tablas AS
SELECT run_id, tabla, filas_leidas, filas_cargadas
FROM audit.etl_run_tablas;
