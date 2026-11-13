-- ==========================================================
-- 006 · Origen 'prueba_calidad' en audit.etl_runs (idempotente)
-- ==========================================================
-- Marca el run en el que se inyectó a propósito un dato inválido para comprobar
-- que un test de calidad fallido detiene el pipeline sin avanzar el watermark.

ALTER TABLE audit.etl_runs DROP CONSTRAINT IF EXISTS etl_runs_origen_check;
ALTER TABLE audit.etl_runs ADD CONSTRAINT etl_runs_origen_check
    CHECK (origen IN ('schedule', 'manual', 'local', 'prueba_idempotencia', 'prueba_calidad'));

-- es_prueba cubre cualquier origen de prueba
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
    COALESCE(SUM(t.filas_cargadas), 0) AS filas_cargadas,
    (r.origen LIKE 'prueba\_%')        AS es_prueba,
    r.nota
FROM audit.etl_runs r
LEFT JOIN audit.etl_run_tablas t USING (run_id)
GROUP BY r.run_id;
