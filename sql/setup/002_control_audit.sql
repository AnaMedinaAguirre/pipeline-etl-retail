-- ==========================================================
-- 002 · Tablas de control y auditoría (idempotente)
-- ==========================================================

-- ----------------------------------------------------------
-- control.watermark: hasta qué fecha de compra se cargó cada fuente.
-- Solo avanza cuando el run completo (carga + dbt + tests) termina bien.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS control.watermark (
    fuente                text        PRIMARY KEY,
    ultima_fecha_cargada  date        NOT NULL,
    run_id                bigint,
    actualizado_en        timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE control.watermark IS
    'Marca de agua del simulador de llegada: última fecha de pedidos cargada por fuente';

-- ----------------------------------------------------------
-- audit.etl_runs: una fila por ejecución del pipeline.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit.etl_runs (
    run_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    iniciado_en     timestamptz NOT NULL DEFAULT now(),
    finalizado_en   timestamptz,
    duracion_seg    numeric(10, 2),
    estado          text        NOT NULL DEFAULT 'en_curso'
                    CHECK (estado IN ('en_curso', 'exito', 'fallido', 'sin_datos')),
    origen          text        NOT NULL DEFAULT 'local'
                    CHECK (origen IN ('schedule', 'manual', 'local')),  -- ampliado en 005
    ventana_desde   date,
    ventana_hasta   date,
    tests_ok        integer,
    tests_fallidos  integer,
    git_sha         text,
    mensaje_error   text,
    CHECK (ventana_desde IS NULL OR ventana_hasta IS NULL OR ventana_desde <= ventana_hasta)
);
COMMENT ON TABLE audit.etl_runs IS 'Bitácora de ejecuciones del pipeline';

CREATE INDEX IF NOT EXISTS ix_etl_runs_iniciado_en ON audit.etl_runs (iniciado_en DESC);

-- ----------------------------------------------------------
-- audit.etl_run_tablas: filas leídas/cargadas por tabla en cada run.
-- (Tabla aparte en vez de JSON para que Power BI la consuma fácil)
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit.etl_run_tablas (
    run_id          bigint  NOT NULL REFERENCES audit.etl_runs (run_id) ON DELETE CASCADE,
    tabla           text    NOT NULL,
    filas_leidas    bigint  NOT NULL DEFAULT 0 CHECK (filas_leidas >= 0),
    filas_cargadas  bigint  NOT NULL DEFAULT 0 CHECK (filas_cargadas >= 0),
    PRIMARY KEY (run_id, tabla)
);
COMMENT ON TABLE audit.etl_run_tablas IS 'Detalle por tabla de cada ejecución';
