"""Ejecuta dbt con las credenciales tomadas de DATABASE_URL.

dbt lee la conexión de dbt/profiles.yml, que solo contiene referencias a
variables de entorno (DBT_HOST, DBT_USER, ...). Este módulo las arma a partir
de la URL de conexión directa, sin escribir secretos en disco.

Uso como CLI (cualquier comando de dbt):
  python -m etl.dbt_cli build
  python -m etl.dbt_cli build --select marts
  python -m etl.dbt_cli docs generate
"""

import logging
import os
import sys
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from etl.config import RAIZ_PROYECTO, obtener_database_url
from etl.logging_config import configurar_logging

log = logging.getLogger(__name__)

DIR_DBT = RAIZ_PROYECTO / "dbt"


@dataclass(frozen=True)
class ResultadoDbt:
    exito: bool
    tests_ok: int = 0
    tests_advertencia: int = 0
    tests_fallidos: int = 0
    modelos_ok: int = 0
    modelos_error: int = 0


def variables_conexion(url: str) -> dict[str, str]:
    """Traduce una URL postgresql:// a las variables que usa profiles.yml."""
    p = urlparse(url)
    if p.scheme not in ("postgres", "postgresql") or not p.hostname:
        raise ValueError(
            "La URL de conexión no tiene el formato postgresql://usuario:clave@host/db"
        )
    return {
        "DBT_HOST": p.hostname,
        "DBT_PORT": str(p.port or 5432),
        "DBT_USER": unquote(p.username or ""),
        "DBT_PASSWORD": unquote(p.password or ""),
        "DBT_DBNAME": p.path.lstrip("/") or "neondb",
    }


def preparar_entorno() -> None:
    """Exporta las variables DBT_* al entorno del proceso (sin imprimirlas)."""
    os.environ.update(variables_conexion(obtener_database_url()))
    # Evita que dbt intente enviar métricas de uso
    os.environ.setdefault("DO_NOT_TRACK", "1")


def resumir(resultados) -> ResultadoDbt:
    """Cuenta modelos y tests por estado a partir del resultado de dbt build."""
    conteo = {"tests_ok": 0, "tests_advertencia": 0, "tests_fallidos": 0,
              "modelos_ok": 0, "modelos_error": 0}  # fmt: skip
    for r in resultados or []:
        tipo = getattr(r.node, "resource_type", "")
        estado = str(r.status)
        if tipo == "test":
            if estado == "pass":
                conteo["tests_ok"] += 1
            elif estado == "warn":
                conteo["tests_advertencia"] += 1
            elif estado in ("fail", "error"):
                conteo["tests_fallidos"] += 1
        elif tipo in ("model", "seed"):
            if estado == "success":
                conteo["modelos_ok"] += 1
            elif estado == "error":
                conteo["modelos_error"] += 1
    return ResultadoDbt(exito=False, **conteo)


def ejecutar_dbt(argumentos: list[str]) -> ResultadoDbt:
    """Ejecuta un comando de dbt en el mismo proceso y devuelve un resumen."""
    from dbt.cli.main import dbtRunner  # import diferido: dbt tarda en cargar

    preparar_entorno()
    rutas = ["--project-dir", str(DIR_DBT), "--profiles-dir", str(DIR_DBT)]

    # Instala paquetes (dbt_utils) si aún no están
    if not (DIR_DBT / "dbt_packages" / "dbt_utils").exists():
        log.info("Instalando paquetes de dbt (dbt deps)…")
        deps = dbtRunner().invoke(["deps", *rutas])
        if not deps.success:
            raise RuntimeError(f"dbt deps falló: {deps.exception}")

    log.info("Ejecutando: dbt %s", " ".join(argumentos))
    res = dbtRunner().invoke([*argumentos, *rutas])
    resultados = getattr(res.result, "results", None)
    resumen = resumir(resultados)
    resumen = ResultadoDbt(**{**resumen.__dict__, "exito": bool(res.success)})
    if res.exception:
        log.error("dbt terminó con excepción: %s", res.exception)
    return resumen


def main() -> int:
    configurar_logging()
    resumen = ejecutar_dbt(sys.argv[1:] or ["build"])
    log.info("Resumen dbt: %s", resumen)
    return 0 if resumen.exito else 1


if __name__ == "__main__":
    sys.exit(main())
