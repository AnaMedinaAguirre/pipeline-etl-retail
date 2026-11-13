"""Tests de utilidades de auditoría y de la lectura de CSV."""

import pytest

from etl.audit import detectar_origen, sanitizar_error
from etl.extract_olist import leer_csv


@pytest.mark.parametrize(
    ("evento", "esperado"),
    [("schedule", "schedule"), ("workflow_dispatch", "manual"), ("", "local"), ("push", "local")],
)
def test_detectar_origen(monkeypatch, evento, esperado):
    monkeypatch.setenv("GITHUB_EVENT_NAME", evento)
    assert detectar_origen() == esperado


def test_sanitizar_error_oculta_cadenas_de_conexion_y_passwords():
    msg = "fallo postgresql://usuario:SECRETO@ep-x.neon.tech/neondb?sslmode=require y password=OTRO"
    limpio = sanitizar_error(msg)
    assert "SECRETO" not in limpio and "OTRO" not in limpio
    assert "postgresql://***" in limpio


def test_sanitizar_error_trunca_mensajes_largos():
    assert len(sanitizar_error("x" * 10_000)) == 2000


def test_leer_csv_conserva_texto_y_solo_vacios_son_nulos(tmp_path):
    ruta = tmp_path / "prueba.csv"
    # BOM inicial, cero a la izquierda, "NA" literal y una celda vacía
    ruta.write_text(
        '﻿zip,ciudad,comentario\n01310,sao paulo,NA\n02020,,"texto, con coma"\n',
        encoding="utf-8",
    )
    df = leer_csv(ruta)
    assert list(df.columns) == ["zip", "ciudad", "comentario"]  # sin BOM
    assert df.loc[0, "zip"] == "01310"  # no se convierte a número
    assert df.loc[0, "comentario"] == "NA"  # "NA" es texto, no nulo
    assert df["ciudad"].isna().tolist() == [False, True]
    assert df.loc[1, "comentario"] == "texto, con coma"
