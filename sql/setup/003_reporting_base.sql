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

-- Salud del pipeline: ejecuciones con total de filas cargadas.
CREATE OR REPLACE VIEW reporting.vw_etl_runs AS
SELECT
    r.run_id,
    r.iniciado_en  AT TIME ZONE 'America/Lima' AS iniciado_en_lima,
    r.finalizado_en AT TIME ZONE 'America/Lima' AS finalizado_en_lima,
    r.duracion_seg,
    r.estado,
    r.origen,
    r.ventana_desde,
    r.ventana_hasta,
    r.tests_ok,
    r.tests_fallidos,
    r.mensaje_error,
    COALESCE(SUM(t.filas_leidas), 0)   AS filas_leidas,
    COALESCE(SUM(t.filas_cargadas), 0) AS filas_cargadas
FROM audit.etl_runs r
LEFT JOIN audit.etl_run_tablas t USING (run_id)
GROUP BY r.run_id;

CREATE OR REPLACE VIEW reporting.vw_etl_run_tablas AS
SELECT run_id, tabla, filas_leidas, filas_cargadas
FROM audit.etl_run_tablas;
