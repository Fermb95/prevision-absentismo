"""
tests/test_segmentacion.py — Micro-segmentación por turno × puesto × carga.
"""
from __future__ import annotations

import importlib
from datetime import date

import pandas as pd
import pytest

from datos_demo.generador import generar_segmentacion_para_db
from ingesta.segmentacion import preparar_persistencia
from ingesta.validacion import validar_absentismo
from modelo.segmentacion import (
    anadir_franjas_carga,
    carga_vs_absentismo,
    focos,
    por_dimension,
    tabla_segmentos,
)

FIN = date(2026, 7, 1)


# ------------------------------ VALIDACIÓN ------------------------------
def test_validacion_acepta_puesto_y_carga():
    df = pd.DataFrame([
        {"centro": "Albacete", "turno": "manana", "anio": 2026, "mes": 1,
         "jornadas_teoricas": 200, "jornadas_perdidas": 20,
         "puesto": "Preparación", "carga": 60},
    ])
    res = validar_absentismo(df)
    assert res.ok
    assert res.df.iloc[0]["puesto"] == "Preparación"
    assert res.df.iloc[0]["carga"] == 60


def test_puesto_no_es_columna_personal():
    from ingesta.validacion import detectar_columnas_personales
    assert detectar_columnas_personales(["puesto", "carga"]) == []


# ------------------------------ AGREGACIÓN ------------------------------
def test_preparar_persistencia_agrega_por_puesto():
    # Dos puestos en el mismo centro/turno/mes → el histórico los agrega.
    df = pd.DataFrame([
        {"centro": "Albacete", "turno": "manana", "anio": 2026, "mes": 1, "periodo": "2026-01",
         "plantilla_media": 20, "jornadas_teoricas": 400, "jornadas_perdidas": 40, "tasa": 0.10,
         "puesto": "Preparación", "carga": 60},
        {"centro": "Albacete", "turno": "manana", "anio": 2026, "mes": 1, "periodo": "2026-01",
         "plantilla_media": 10, "jornadas_teoricas": 200, "jornadas_perdidas": 10, "tasa": 0.05,
         "puesto": "Recepción", "carga": 30},
    ])
    hist, seg = preparar_persistencia(df)
    assert len(hist) == 1  # un solo centro/turno/periodo
    # tasa agregada = (40+10)/(400+200) = 50/600
    assert hist.iloc[0]["tasa"] == pytest.approx(50 / 600, abs=1e-5)
    assert hist.iloc[0]["jornadas_perdidas"] == 50
    assert len(seg) == 2  # detalle por puesto


def test_preparar_persistencia_sin_puesto():
    df = pd.DataFrame([
        {"centro": "X", "turno": "manana", "anio": 2026, "mes": 1, "periodo": "2026-01",
         "plantilla_media": 20, "jornadas_teoricas": 400, "jornadas_perdidas": 40, "tasa": 0.10},
    ])
    hist, seg = preparar_persistencia(df)
    assert len(hist) == 1 and seg.empty


# ------------------------------ ANÁLISIS ------------------------------
def test_tabla_segmentos_y_focos():
    seg = generar_segmentacion_para_db(FIN)
    tabla = tabla_segmentos(seg, centro="Valencia")
    assert not tabla.empty
    assert {"tasa_media", "jornadas_perdidas_mes", "carga_media", "plantilla"} <= set(tabla.columns)
    # Los focos se ordenan por impacto (jornadas perdidas/mes) descendente.
    f = focos(tabla, top=3)
    assert f["jornadas_perdidas_mes"].is_monotonic_decreasing


def test_franjas_y_dimension():
    seg = generar_segmentacion_para_db(FIN)
    tabla = anadir_franjas_carga(tabla_segmentos(seg))
    assert "franja" in tabla.columns
    dim = por_dimension(tabla, "puesto")
    assert not dim.empty
    assert "tasa_media" in dim.columns


def test_carga_correlaciona_con_absentismo():
    # En el demo, la carga influye positivamente: correlación > 0.
    seg = generar_segmentacion_para_db(FIN)
    tabla = tabla_segmentos(seg)
    corr = carga_vs_absentismo(tabla)
    assert corr > 0


# ------------------------------ PERSISTENCIA ------------------------------
@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    import config
    importlib.reload(config)
    for m in ("persistencia.db", "persistencia.segmentacion"):
        importlib.reload(importlib.import_module(m))
    from persistencia import db
    db.inicializar_esquema(modo="real")
    from persistencia import segmentacion
    return segmentacion


def test_persistencia_segmentacion(entorno):
    segmentacion = entorno
    seg = generar_segmentacion_para_db(FIN)
    n = segmentacion.guardar_segmentacion(seg, modo="real")
    assert n == len(seg)
    assert segmentacion.hay_segmentacion(modo="real")
    leido = segmentacion.leer_segmentacion(centro="Valencia", modo="real")
    assert not leido.empty
    assert set(leido["puesto"].unique()) <= {
        "Preparación", "Carretillero", "Recepción", "Administración"
    }
