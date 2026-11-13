"""Extracción de tipos de cambio oficiales (APIs públicas, sin API key).

- BCB (Banco Central do Brasil), SGS serie 1: dólar PTAX venta, en BRL por USD (diaria).
- BCRP (Banco Central de Reserva del Perú), PD04640PD: TC sistema bancario SBS venta,
  en S/ por USD (diaria).
- BCRP PN01225XM: real brasileño por USD, promedio mensual (para validar la serie del BCB).

Las APIs solo publican días hábiles. El relleno de fines de semana y feriados
(con marca `es_imputado`) se hace en la capa de transformación (dbt).
"""

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

URL_BCRP = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{serie}/json/{desde}/{hasta}"
URL_BCB = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados"

SERIE_BCB_USD_BRL = "1"  # PTAX venta
SERIE_BCRP_PEN_USD = "PD04640PD"  # S/ por US$, venta, sistema bancario SBS
SERIE_BCRP_BRL_USD_MENSUAL = "PN01225XM"  # R$ por US$, promedio del mes

# El BCRP usa abreviaturas en español; la serie diaria escribe septiembre como "Set"
# y la mensual como "Sep", así que se aceptan ambas.
MESES_BCRP = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}  # fmt: skip

TIMEOUT_SEG = 60


@dataclass(frozen=True)
class Observacion:
    """Un valor de una serie de tipo de cambio, tal cual lo publica la fuente."""

    fuente: str
    serie: str
    fecha: date  # para series mensuales: primer día del mes
    fecha_original: str
    valor_original: str


# ----------------------------------------------------------------------
# Parsers (funciones puras, cubiertas por pytest)
# ----------------------------------------------------------------------
def parsear_fecha_bcrp_diaria(texto: str) -> date:
    """'02.Ene.17' -> date(2017, 1, 2)."""
    try:
        dia, mes, anio = texto.strip().split(".")
        return date(2000 + int(anio), MESES_BCRP[mes.lower()], int(dia))
    except (ValueError, KeyError) as exc:
        raise ValueError(f"Fecha diaria BCRP no reconocida: {texto!r}") from exc


def parsear_periodo_bcrp_mensual(texto: str) -> date:
    """'Ene.2017' -> date(2017, 1, 1)."""
    try:
        mes, anio = texto.strip().split(".")
        return date(int(anio), MESES_BCRP[mes.lower()], 1)
    except (ValueError, KeyError) as exc:
        raise ValueError(f"Periodo mensual BCRP no reconocido: {texto!r}") from exc


def parsear_respuesta_bcrp(contenido: dict, serie: str, mensual: bool = False) -> list[Observacion]:
    """Convierte la respuesta JSON del BCRP en observaciones.

    Se conserva el valor como texto (puede ser 'n.d.'); se descarta en dbt.
    """
    parsear = parsear_periodo_bcrp_mensual if mensual else parsear_fecha_bcrp_diaria
    observaciones = []
    for periodo in contenido.get("periods", []):
        etiqueta = periodo["name"]
        valores = periodo.get("values") or [None]
        observaciones.append(Observacion("BCRP", serie, parsear(etiqueta), etiqueta, valores[0]))
    return observaciones


def parsear_respuesta_bcb(contenido: list, serie: str) -> list[Observacion]:
    """Convierte la respuesta JSON del BCB ([{'data': 'dd/mm/aaaa', 'valor': 'x.xxxx'}])."""
    return [
        Observacion(
            "BCB",
            f"SGS{serie}",
            datetime.strptime(item["data"], "%d/%m/%Y").date(),
            item["data"],
            item.get("valor"),
        )
        for item in contenido
    ]


# ----------------------------------------------------------------------
# Llamadas HTTP
# ----------------------------------------------------------------------
def _sesion() -> requests.Session:
    """Sesión HTTP con reintentos exponenciales ante errores transitorios."""
    reintentos = Retry(
        total=4,
        backoff_factor=2,  # 0, 2, 4, 8 s
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    sesion = requests.Session()
    sesion.mount("https://", HTTPAdapter(max_retries=reintentos))
    sesion.headers["User-Agent"] = "pipeline-etl-retail/1.0"
    return sesion


def obtener_bcrp(serie: str, desde: date, hasta: date, mensual: bool = False) -> list[Observacion]:
    """Descarga una serie del BCRP entre dos fechas."""
    if mensual:
        rango = (f"{desde.year}-{desde.month}", f"{hasta.year}-{hasta.month}")
    else:
        rango = (desde.isoformat(), hasta.isoformat())
    url = URL_BCRP.format(serie=serie, desde=rango[0], hasta=rango[1])

    with _sesion() as sesion:
        resp = sesion.get(url, timeout=TIMEOUT_SEG)
    resp.raise_for_status()
    # El BCRP responde JSON pero con Content-Type text/html: se decodifica manualmente
    try:
        texto = resp.content.decode("utf-8")
    except UnicodeDecodeError:
        texto = resp.content.decode("latin-1")
    try:
        contenido = json.loads(texto)
    except json.JSONDecodeError:
        # Sin datos en el rango, el BCRP puede devolver una página HTML
        log.warning("BCRP %s sin datos JSON entre %s y %s", serie, *rango)
        return []

    obs = parsear_respuesta_bcrp(contenido, serie, mensual=mensual)
    log.info("BCRP %s: %d observaciones (%s → %s)", serie, len(obs), *rango)
    return obs


def obtener_bcb(serie: str, desde: date, hasta: date) -> list[Observacion]:
    """Descarga una serie del SGS del BCB entre dos fechas."""
    params = {
        "formato": "json",
        "dataInicial": desde.strftime("%d/%m/%Y"),
        "dataFinal": hasta.strftime("%d/%m/%Y"),
    }
    with _sesion() as sesion:
        resp = sesion.get(URL_BCB.format(serie=serie), params=params, timeout=TIMEOUT_SEG)
    # El BCB responde 404 "Value(s) not found" cuando el rango no tiene días hábiles
    if resp.status_code == 404:
        log.warning("BCB SGS%s sin datos entre %s y %s", serie, desde, hasta)
        return []
    resp.raise_for_status()

    obs = parsear_respuesta_bcb(resp.json(), serie)
    log.info("BCB SGS%s: %d observaciones (%s → %s)", serie, len(obs), desde, hasta)
    return obs
