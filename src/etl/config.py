"""Lectura de configuración desde variables de entorno.

Orden de carga (sin sobrescribir lo que ya existe en el entorno):
  1. Variables del sistema (en GitHub Actions vienen de los Secrets).
  2. .env.local  -> opcional (neon deploy lo usa solo si no existe .env).
  3. .env        -> DATABASE_URL* (de `neon deploy`), Kaggle y parámetros del simulador.

Nunca se imprimen secretos: usa `describir_conexion()` para logs.
"""

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]

# override=False: lo que ya está en el entorno tiene prioridad
for _archivo in (".env.local", ".env"):
    load_dotenv(RAIZ_PROYECTO / _archivo, override=False)


class ConfigError(RuntimeError):
    """Falta o es inválida una variable de configuración."""


def obtener_database_url() -> str:
    """URL de conexión DIRECTA (sin pooler) a Postgres.

    `neon deploy` escribe dos variables en .env.local:
      - DATABASE_URL_UNPOOLED -> conexión directa (la que usamos para COPY y dbt)
      - DATABASE_URL          -> conexión por pooler (PgBouncer)
    En GitHub Actions solo existe el secret DATABASE_URL, con la cadena directa.
    """
    for nombre in ("DATABASE_URL_UNPOOLED", "DATABASE_URL"):
        valor = os.getenv(nombre, "").strip()
        if valor:
            return valor
    raise ConfigError(
        "Falta DATABASE_URL_UNPOOLED/DATABASE_URL. Ejecuta `neon deploy` (local) "
        "o revisa los Secrets del repositorio (GitHub Actions)."
    )


def _requerida(nombre: str) -> str:
    valor = os.getenv(nombre, "").strip()
    if not valor:
        raise ConfigError(
            f"Falta la variable de entorno {nombre}. Revisa tu .env/.env.local "
            "(local) o los Secrets del repositorio (GitHub Actions)."
        )
    return valor


@dataclass(frozen=True)
class Config:
    """Parámetros del pipeline."""

    database_url: str
    batch_days: int
    fecha_carga_inicial: date
    dir_datos: Path


def cargar_config() -> Config:
    """Construye la configuración validando tipos básicos."""
    try:
        batch_days = int(os.getenv("BATCH_DAYS", "7"))
        fecha_inicial = date.fromisoformat(os.getenv("FECHA_CARGA_INICIAL", "2017-12-31"))
    except ValueError as exc:
        raise ConfigError(f"Parámetro del simulador inválido: {exc}") from exc
    if batch_days < 1:
        raise ConfigError("BATCH_DAYS debe ser >= 1")

    return Config(
        database_url=obtener_database_url(),
        batch_days=batch_days,
        fecha_carga_inicial=fecha_inicial,
        dir_datos=RAIZ_PROYECTO / "data",
    )


def describir_conexion(url: str) -> str:
    """Devuelve una descripción segura (sin usuario ni contraseña) para logs."""
    partes = urlparse(url)
    host = partes.hostname or "?"
    # Solo se muestra el inicio del endpoint, nunca la cadena completa
    host_corto = host.split(".")[0][:12] + "…"
    base = partes.path.lstrip("/") or "?"
    return f"host={host_corto} db={base}"
