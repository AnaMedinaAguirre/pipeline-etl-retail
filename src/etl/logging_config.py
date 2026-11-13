"""Configuración centralizada de logging para todo el pipeline."""

import logging
import os
import sys

_FORMATO = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def configurar_logging(nivel: str | None = None) -> None:
    """Configura el logger raíz una sola vez.

    El nivel se toma del argumento, de la variable LOG_LEVEL o, por defecto, INFO.
    Los logs salen por stdout para que GitHub Actions los muestre en orden.
    """
    nivel = (nivel or os.getenv("LOG_LEVEL", "INFO")).upper()
    raiz = logging.getLogger()
    if raiz.handlers:  # ya configurado: no duplicar handlers
        raiz.setLevel(nivel)
        return

    # En Windows, si la salida se redirige (pipe/archivo), Python usa cp1252 y
    # caracteres como "→" o "✔" rompen el log. Se fuerza UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMATO, datefmt=_FORMATO_FECHA))
    raiz.addHandler(handler)
    raiz.setLevel(nivel)

    # Librerías ruidosas: solo advertencias
    for ruidoso in ("urllib3", "requests"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
