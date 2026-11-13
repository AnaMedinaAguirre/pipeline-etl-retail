-- ==========================================================
-- 005 · Runs de prueba en audit.etl_runs (idempotente)
-- ==========================================================
-- Permite distinguir ejecuciones de verificación (p. ej. el reproceso manual
-- que demuestra la idempotencia) de las cargas normales, para que no se
-- confundan con cargas duplicadas en la página "Salud del pipeline".

-- Nuevo valor permitido en origen: 'prueba_idempotencia'
ALTER TABLE audit.etl_runs DROP CONSTRAINT IF EXISTS etl_runs_origen_check;
ALTER TABLE audit.etl_runs ADD CONSTRAINT etl_runs_origen_check
    CHECK (origen IN ('schedule', 'manual', 'local', 'prueba_idempotencia'));

-- Nota libre que explica un run especial
ALTER TABLE audit.etl_runs ADD COLUMN IF NOT EXISTS nota text;

-- La vista agrega es_prueba y nota (al final, como exige CREATE OR REPLACE VIEW)
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
    (r.origen = 'prueba_idempotencia') AS es_prueba,
    r.nota
FROM audit.etl_runs r
LEFT JOIN audit.etl_run_tablas t USING (run_id)
GROUP BY r.run_id;
