"""
tests/test_factores.py — Validación, persistencia y análisis de factores.
"""
from __future__ import annotations

import importlib
from datetime import date

import pandas as pd
import pytest

from datos_demo.generador import generar_factores_para_db, generar_historico_para_db
from ingesta.validacion import validar_absentismo
from modelo.factores import (
    comparar_flexibilidad_rotacion,
    ranking_factores,
    tabla_factores_absentismo,
)

FIN = date(2026, 7, 1)


# ------------------------------ VALIDACIÓN ------------------------------
def test_validacion_acepta_factores():
    df = pd.DataFrame([
        {"centro": "A", "turno": "manana", "anio": 2026, "mes": 1,
         "jornadas_teoricas": 200, "jornadas_perdidas": 20,
         "tipo_horario": "Flexible", "rotacion_pct": 12, "antiguedad_media": 8,
         "satisfaccion_media": 7.5, "jornada_media": 160},
    ])
    res = validar_absentismo(df)
    assert res.ok
    assert res.df.iloc[0]["tipo_horario"] == "flexible"  # normalizado
    for c in ("rotacion_pct", "antiguedad_media", "satisfaccion_media", "jornada_media"):
        assert c in res.df.columns


def test_validacion_rechaza_tipo_horario_invalido():
    df = pd.DataFrame([
        {"centro": "A", "turno": "manana", "anio": 2026, "mes": 1,
         "jornadas_teoricas": 200, "jornadas_perdidas": 20, "tipo_horario": "mixto"},
    ])
    res = validar_absentismo(df)
    assert not res.ok
    assert any("tipo_horario" in e for e in res.errores)


def test_factores_no_son_columnas_personales():
    # Los factores agregados no deben disparar la barrera de privacidad.
    from ingesta.validacion import detectar_columnas_personales
    from config import COLUMNAS_FACTORES
    assert detectar_columnas_personales(list(COLUMNAS_FACTORES)) == []


# ------------------------------ ANÁLISIS ------------------------------
def test_tabla_y_flexibilidad_rotacion():
    hist = generar_historico_para_db(FIN)
    fac = generar_factores_para_db(FIN)
    tabla = tabla_factores_absentismo(hist, fac)
    assert not tabla.empty
    assert {"tasa_media", "tipo_horario"} <= set(tabla.columns)

    comp = comparar_flexibilidad_rotacion(tabla[tabla["turno"] != "todos"])
    tipos = set(comp["tipo_horario"])
    assert {"flexible", "rotativo"} <= tipos
    # En el demo, los rotativos deben salir con más absentismo que los flexibles.
    media = comp.set_index("tipo_horario")["tasa_media"]
    assert media["rotativo"] > media["flexible"]


def test_ranking_factores_ordena_por_asociacion():
    hist = generar_historico_para_db(FIN)
    fac = generar_factores_para_db(FIN)
    tabla = tabla_factores_absentismo(hist, fac)
    rank = ranking_factores(tabla[tabla["turno"] != "todos"])
    assert not rank.empty
    assert "correlacion" in rank.columns
    # La satisfacción debe asociarse NEGATIVAMENTE con el absentismo en el demo.
    fila_sat = rank[rank["factor"] == "satisfaccion_media"]
    assert not fila_sat.empty
    assert fila_sat.iloc[0]["correlacion"] < 0


# ------------------------------ PERSISTENCIA ------------------------------
@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    import config
    importlib.reload(config)
    for m in ("persistencia.db", "persistencia.factores"):
        importlib.reload(importlib.import_module(m))
    from persistencia import db
    db.inicializar_esquema(modo="real")
    from persistencia import factores
    return factores


def test_persistencia_factores_upsert(entorno):
    factores = entorno
    fac = generar_factores_para_db(FIN)
    n = factores.guardar_factores(fac, modo="real")
    assert n == len(fac)
    assert factores.hay_factores(modo="real")
    leido = factores.leer_factores(centro="Valencia", turno="noche", modo="real")
    assert not leido.empty
    assert leido.iloc[0]["tipo_horario"] == "rotativo"
