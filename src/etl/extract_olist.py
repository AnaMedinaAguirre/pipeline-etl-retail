"""Extracción del dataset Olist desde Kaggle.

Dataset: "Brazilian E-Commerce Public Dataset by Olist" (olistbr/brazilian-ecommerce),
licencia CC BY-NC-SA 4.0. Los CSV se guardan en data/olist/ (ignorado por git) y
no se redistribuyen en el repositorio.

Credenciales: KAGGLE_USERNAME y KAGGLE_KEY (en .env o en GitHub Secrets).
"""

import hashlib
import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

DATASET_KAGGLE = "olistbr/brazilian-ecommerce"

# Nombre lógico -> archivo CSV. La geolocalización se excluye a propósito
# (1 M de filas que no se usan: el mapa se hace por estado/UF).
ARCHIVOS = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}


def _faltantes(directorio: Path) -> list[str]:
    return [
        archivo
        for archivo in ARCHIVOS.values()
        if not (directorio / archivo).is_file() or (directorio / archivo).stat().st_size == 0
    ]


def descargar_dataset(directorio: Path, forzar: bool = False) -> None:
    """Descarga y descomprime el dataset si falta algún archivo (o si se fuerza)."""
    directorio.mkdir(parents=True, exist_ok=True)
    faltan = _faltantes(directorio)
    if not faltan and not forzar:
        log.info("Dataset Olist ya presente en %s (se reutiliza)", directorio)
        return

    log.info("Descargando %s desde Kaggle (faltan %d archivos)…", DATASET_KAGGLE, len(faltan))
    # Import diferido: la librería de Kaggle se autentica al importarse
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    api.dataset_download_files(DATASET_KAGGLE, path=str(directorio), unzip=True, quiet=True)

    faltan = _faltantes(directorio)
    if faltan:
        raise FileNotFoundError(f"Tras la descarga siguen faltando archivos: {faltan}")
    log.info("Descarga completa")


def huella(ruta: Path) -> str:
    """SHA-256 abreviado del archivo, para trazabilidad en los logs."""
    sha = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            sha.update(bloque)
    return sha.hexdigest()[:12]


def leer_csv(ruta: Path) -> pd.DataFrame:
    """Lee un CSV de Olist sin alterar los valores.

    - Todo como texto (dtype=str): la capa raw guarda los datos tal cual.
    - Solo las celdas vacías se tratan como nulo (no 'NA', 'null', etc.).
    - utf-8-sig elimina el BOM que trae algún archivo.
    """
    return pd.read_csv(ruta, dtype=str, keep_default_na=False, na_values=[""], encoding="utf-8-sig")


def leer_dataset(directorio: Path) -> dict[str, pd.DataFrame]:
    """Lee todos los CSV del dataset y registra filas y huella de cada uno."""
    datos = {}
    for nombre, archivo in ARCHIVOS.items():
        ruta = directorio / archivo
        datos[nombre] = leer_csv(ruta)
        log.info("Leído %-38s %8d filas  sha256=%s", archivo, len(datos[nombre]), huella(ruta))
    return datos
