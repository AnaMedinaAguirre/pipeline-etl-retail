"""Tests del puente Python -> dbt (sin ejecutar dbt ni conectarse a la base)."""

from types import SimpleNamespace

import pytest

from etl.dbt_cli import resumir, variables_conexion


def test_variables_conexion_desde_url():
    v = variables_conexion(
        "postgresql://usuario:cl%40ve@ep-x.sa-east-1.aws.neon.tech/neondb?sslmode=require"
    )
    assert v == {
        "DBT_HOST": "ep-x.sa-east-1.aws.neon.tech",
        "DBT_PORT": "5432",
        "DBT_USER": "usuario",
        "DBT_PASSWORD": "cl@ve",  # se decodifica el %40
        "DBT_DBNAME": "neondb",
    }


def test_variables_conexion_respeta_puerto():
    assert variables_conexion("postgres://u:p@host:6543/db")["DBT_PORT"] == "6543"


@pytest.mark.parametrize("url", ["mysql://u:p@h/db", "no-es-una-url"])
def test_variables_conexion_rechaza_urls_invalidas(url):
    with pytest.raises(ValueError):
        variables_conexion(url)


def _r(tipo: str, estado: str):
    return SimpleNamespace(node=SimpleNamespace(resource_type=tipo), status=estado)


def test_resumir_cuenta_tests_y_modelos_por_estado():
    resumen = resumir(
        [
            _r("test", "pass"),
            _r("test", "pass"),
            _r("test", "warn"),
            _r("test", "fail"),
            _r("test", "error"),
            _r("model", "success"),
            _r("seed", "success"),
            _r("model", "error"),
            _r("model", "skipped"),
        ]
    )
    assert (resumen.tests_ok, resumen.tests_advertencia, resumen.tests_fallidos) == (2, 1, 2)
    assert (resumen.modelos_ok, resumen.modelos_error) == (2, 1)


def test_resumir_sin_resultados():
    assert resumir(None).tests_ok == 0
