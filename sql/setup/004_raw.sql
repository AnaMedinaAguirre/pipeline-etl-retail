-- ==========================================================
-- 004 · Capa RAW (idempotente)
-- ==========================================================
-- Los datos se guardan "tal cual llegan": todas las columnas de negocio
-- son TEXT, con los nombres originales del CSV (incluidas las erratas de
-- Olist, p. ej. product_name_lenght). El tipado y la limpieza se hacen en
-- staging (dbt).
--
-- Columnas de metadatos en cada tabla:
--   _run_id        ejecución que cargó la fila (audit.etl_runs)
--   _ventana_desde ventana del simulador a la que pertenece la fila
--   _ventana_hasta
--   _cargado_en    momento de la carga
-- ==========================================================

-- ---------------- Olist: tablas ligadas al pedido ----------------
CREATE TABLE IF NOT EXISTS raw.olist_orders (
    order_id                       text,
    customer_id                    text,
    order_status                   text,
    order_purchase_timestamp       text,
    order_approved_at              text,
    order_delivered_carrier_date   text,
    order_delivered_customer_date  text,
    order_estimated_delivery_date  text,
    _run_id        bigint,
    _ventana_desde date,
    _ventana_hasta date,
    _cargado_en    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.olist_order_items (
    order_id             text,
    order_item_id        text,
    product_id           text,
    seller_id            text,
    shipping_limit_date  text,
    price                text,
    freight_value        text,
    _run_id        bigint,
    _ventana_desde date,
    _ventana_hasta date,
    _cargado_en    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.olist_order_payments (
    order_id              text,
    payment_sequential    text,
    payment_type          text,
    payment_installments  text,
    payment_value         text,
    _run_id        bigint,
    _ventana_desde date,
    _ventana_hasta date,
    _cargado_en    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.olist_order_reviews (
    review_id                text,
    order_id                 text,
    review_score             text,
    review_comment_title     text,
    review_comment_message   text,
    review_creation_date     text,
    review_answer_timestamp  text,
    _run_id        bigint,
    _ventana_desde date,
    _ventana_hasta date,
    _cargado_en    timestamptz NOT NULL DEFAULT now()
);

-- ---------------- Olist: entidades referenciadas ----------------
CREATE TABLE IF NOT EXISTS raw.olist_customers (
    customer_id               text,
    customer_unique_id        text,
    customer_zip_code_prefix  text,
    customer_city             text,
    customer_state            text,
    _run_id        bigint,
    _ventana_desde date,
    _ventana_hasta date,
    _cargado_en    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.olist_products (
    product_id                  text,
    product_category_name       text,
    product_name_lenght         text,
    product_description_lenght  text,
    product_photos_qty          text,
    product_weight_g            text,
    product_length_cm           text,
    product_height_cm           text,
    product_width_cm            text,
    _run_id        bigint,
    _ventana_desde date,
    _ventana_hasta date,
    _cargado_en    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.olist_sellers (
    seller_id               text,
    seller_zip_code_prefix  text,
    seller_city             text,
    seller_state            text,
    _run_id        bigint,
    _ventana_desde date,
    _ventana_hasta date,
    _cargado_en    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.olist_category_translation (
    product_category_name          text,
    product_category_name_english  text,
    _run_id        bigint,
    _ventana_desde date,
    _ventana_hasta date,
    _cargado_en    timestamptz NOT NULL DEFAULT now()
);

-- Índices por clave natural: el loader borra por estas columnas antes de reinsertar
CREATE INDEX IF NOT EXISTS ix_raw_orders_order_id    ON raw.olist_orders (order_id);
CREATE INDEX IF NOT EXISTS ix_raw_items_order_id     ON raw.olist_order_items (order_id);
CREATE INDEX IF NOT EXISTS ix_raw_payments_order_id  ON raw.olist_order_payments (order_id);
CREATE INDEX IF NOT EXISTS ix_raw_reviews_order_id   ON raw.olist_order_reviews (order_id);
CREATE INDEX IF NOT EXISTS ix_raw_customers_id       ON raw.olist_customers (customer_id);
CREATE INDEX IF NOT EXISTS ix_raw_products_id        ON raw.olist_products (product_id);
CREATE INDEX IF NOT EXISTS ix_raw_sellers_id         ON raw.olist_sellers (seller_id);

-- ---------------- Tipos de cambio ----------------
-- Diario: BCB (USD/BRL, PTAX venta, serie SGS 1) y BCRP (PEN/USD, PD04640PD).
-- Solo vienen días hábiles; el relleno de fines de semana/feriados se hace en dbt.
CREATE TABLE IF NOT EXISTS raw.tipo_cambio_diario (
    fuente          text NOT NULL,          -- 'BCB' | 'BCRP'
    serie           text NOT NULL,          -- 'SGS1' | 'PD04640PD'
    fecha           date NOT NULL,
    fecha_original  text,                   -- etiqueta tal cual la API ('02.Ene.17', '02/01/2017')
    valor_original  text,                   -- texto tal cual (puede ser 'n.d.')
    _run_id         bigint,
    _cargado_en     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (serie, fecha)
);

-- Mensual: BCRP PN01225XM (BRL por USD, promedio) para validar la serie diaria del BCB.
CREATE TABLE IF NOT EXISTS raw.tipo_cambio_mensual (
    fuente            text NOT NULL,
    serie             text NOT NULL,
    periodo           date NOT NULL,        -- primer día del mes
    periodo_original  text,                 -- 'Ene.2017'
    valor_original    text,
    _run_id           bigint,
    _cargado_en       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (serie, periodo)
);
