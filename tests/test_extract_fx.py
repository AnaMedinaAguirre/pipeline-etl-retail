"""Tests de los parsers de tipo de cambio (respuestas reales de las APIs como fixtures)."""

from datetime import date

import pytest

from etl.extract_fx import (
    parsear_fecha_bcrp_diaria,
    parsear_periodo_bcrp_mensual,
    parsear_respuesta_bcb,
    parsear_respuesta_bcrp,
)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("02.Ene.17", date(2017, 1, 2)),
        ("01.Set.17", date(2017, 9, 1)),  # el BCRP diario usa "Set" para septiembre
        ("30.Dic.16", date(2016, 12, 30)),
        ("15.Ago.18", date(2018, 8, 15)),
    ],
)
def test_fecha_bcrp_diaria(texto, esperado):
    assert parsear_fecha_bcrp_diaria(texto) == esperado


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Ene.2017", date(2017, 1, 1)),
        ("Sep.2017", date(2017, 9, 1)),  # el BCRP mensual usa "Sep"
        ("Set.2017", date(2017, 9, 1)),
        ("Dic.2018", date(2018, 12, 1)),
    ],
)
def test_periodo_bcrp_mensual(texto, esperado):
    assert parsear_periodo_bcrp_mensual(texto) == esperado


@pytest.mark.parametrize("texto", ["2017-01-02", "02.Xyz.17", "", "02.Ene"])
def test_fecha_bcrp_invalida_lanza_error(texto):
    with pytest.raises(ValueError):
        parsear_fecha_bcrp_diaria(texto)


def test_respuesta_bcrp_conserva_valor_original_incluido_nd():
    respuesta = {
        "config": {"title": "Tipo de cambio"},
        "periods": [
            {"name": "02.Ene.17", "values": ["3.363"]},
            {"name": "03.Ene.17", "values": ["n.d."]},
        ],
    }
    obs = parsear_respuesta_bcrp(respuesta, "PD04640PD")
    assert [(o.fecha, o.valor_original) for o in obs] == [
        (date(2017, 1, 2), "3.363"),
        (date(2017, 1, 3), "n.d."),
    ]
    assert obs[0].fuente == "BCRP" and obs[0].fecha_original == "02.Ene.17"


def test_respuesta_bcrp_sin_periodos_devuelve_lista_vacia():
    assert parsear_respuesta_bcrp({"config": {}}, "PD04640PD") == []


def test_respuesta_bcb():
    respuesta = [
        {"data": "02/01/2017", "valor": "3.2729"},
        {"data": "03/01/2017", "valor": "3.2632"},
    ]
    obs = parsear_respuesta_bcb(respuesta, "1")
    assert obs[0].fecha == date(2017, 1, 2)
    assert obs[0].serie == "SGS1" and obs[0].fuente == "BCB"
    assert obs[1].valor_original == "3.2632"
