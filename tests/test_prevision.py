"""
tests/test_prevision.py — Modelo, backtest y recálculo.

Cubre: generación de previsión con esquema correcto, intervalo que se ensancha
con el horizonte, degradación elegante con poco histórico, backtest temporal, y
que recalcular AÑADE tanda (no sobrescribe).
"""
from __future__ import annotations

import importlib
from datetime import date

import numpy as np
import pandas as pd
import pytest

from datos_demo.generador import generar_historico_para_db
from modelo.motor import ModeloEstacionalNaive, serie_mensual, siguientes_periodos
from modelo.prevision import calcular_prevision


FIN = date(2026, 7, 1)


def _hist_demo() -> pd.DataFrame:
    return generar_historico_para_db(FIN)


# ------------------------------- MOTOR NAIVE -------------------------------
def test_naive_predice_y_ensancha_intervalo():
    hist = _hist_demo()
    ct = hist[(hist.centro == "Valencia") & (hist.turno == "noche")]
    serie = serie_mensual(ct)
    modelo = ModeloEstacionalNaive()
    modelo.ajustar(serie)
    periodos = siguientes_periodos(serie.index[-1].strftime("%Y-%m"), 6)
    prev = modelo.prever(periodos)

    assert list(prev.columns) == ["periodo_objetivo", "valor", "lo", "hi"]
    assert len(prev) == 6
    # Intervalo válido y creciente con el horizonte.
    anchos = (prev["hi"] - prev["lo"]).to_numpy()
    assert (anchos > 0).all()
    assert anchos[-1] > anchos[0], "El intervalo debe ensancharse con el horizonte."
    # Valores en rango de tasa.
    assert (prev["valor"] >= 0).all() and (prev["valor"] <= 1).all()


def test_naive_capta_pico_invierno():
    # Serie con estacionalidad marcada: predicción de enero > julio.
    hist = _hist_demo()
    ct = hist[(hist.centro == "Sevilla") & (hist.turno == "todos")]
    serie = serie_mensual(ct)
    modelo = ModeloEstacionalNaive()
    modelo.ajustar(serie)
    # Predecimos hasta cubrir un enero y un julio.
    periodos = siguientes_periodos(serie.index[-1].strftime("%Y-%m"), 12)
    prev = modelo.prever(periodos).set_index("periodo_objetivo")["valor"]
    eneros = [p for p in prev.index if p.endswith("-01")]
    julios = [p for p in prev.index if p.endswith("-07")]
    if eneros and julios:
        assert prev[eneros[0]] > prev[julios[0]]


# ------------------------------- MOTOR SARIMA -------------------------------
def test_sarima_si_disponible():
    """Si statsmodels está instalado, SARIMA debe ajustar y ensanchar el intervalo."""
    pytest.importorskip("statsmodels")
    from modelo.motor import ModeloSARIMA

    hist = _hist_demo()
    ct = hist[(hist.centro == "Zaragoza") & (hist.turno == "noche")]
    serie = serie_mensual(ct)
    modelo = ModeloSARIMA()
    modelo.ajustar(serie)
    periodos = siguientes_periodos(serie.index[-1].strftime("%Y-%m"), 6)
    prev = modelo.prever(periodos)
    assert list(prev.columns) == ["periodo_objetivo", "valor", "lo", "hi"]
    anchos = (prev["hi"] - prev["lo"]).to_numpy()
    assert (anchos > 0).all()
    assert anchos[-1] >= anchos[0]
    assert (prev["valor"] >= 0).all()


# --------------------------- ORQUESTADOR / DEGRADACIÓN ---------------------------
def test_prevision_completa_esquema():
    hist = _hist_demo()
    res = calcular_prevision(hist, motor="prophet", horizonte=6)
    prev = res.previsiones
    assert set(prev.columns) == {
        "centro", "turno", "periodo_objetivo", "valor", "lo", "hi", "modelo"
    }
    # 6 centros × 4 turnos × 6 meses.
    assert len(prev) == 6 * 4 * 6
    assert (prev["lo"] <= prev["valor"]).all()
    assert (prev["valor"] <= prev["hi"]).all()


def test_degradacion_con_poco_historico():
    # Serie de 3 meses: debe usar naive y avisar de baja fiabilidad, sin romper.
    hist = pd.DataFrame(
        [
            {"centro": "Nuevo", "turno": "manana", "periodo": "2026-05", "tasa": 0.05},
            {"centro": "Nuevo", "turno": "manana", "periodo": "2026-06", "tasa": 0.06},
            {"centro": "Nuevo", "turno": "manana", "periodo": "2026-07", "tasa": 0.055},
        ]
    )
    res = calcular_prevision(hist, motor="prophet", horizonte=3)
    assert not res.previsiones.empty
    assert res.detalle.iloc[0]["fiabilidad"] == "baja"
    assert res.detalle.iloc[0]["modelo_usado"] == "naive"
    assert any("naive" in a for a in res.avisos)


# ------------------------------- MÉTRICAS -------------------------------
def test_metricas_error():
    from modelo.metricas import mape, resumen_error, sesgo

    real = pd.Series([0.10, 0.10, 0.10], index=["2026-01", "2026-02", "2026-03"])
    pred = pd.Series([0.11, 0.12, 0.09], index=["2026-01", "2026-02", "2026-03"])
    # Errores: 10%, 20%, 10% → MAPE ~13.33%
    assert mape(real, pred) == pytest.approx((0.1 + 0.2 + 0.1) / 3 * 100, rel=1e-6)
    # Sesgo medio = ((0.01)+(0.02)+(-0.01))/3
    assert sesgo(real, pred) == pytest.approx((0.01 + 0.02 - 0.01) / 3)
    r = resumen_error(real, pred)
    assert r.n == 3 and r.mape > 0


def test_alerta_deriva():
    from modelo.metricas import alerta_deriva

    idx = ["2026-01", "2026-02", "2026-03", "2026-04"]
    real = pd.Series([0.10, 0.10, 0.10, 0.10], index=idx)
    # Predicciones muy desviadas los últimos 3 meses (>20% error).
    pred = pd.Series([0.10, 0.14, 0.15, 0.13], index=idx)
    hay, msg = alerta_deriva(real, pred)
    assert hay is True
    assert "Deriva" in msg


# ------------------------------- BACKTEST -------------------------------
def test_backtest_temporal():
    from modelo.backtest import backtest_punto

    hist = _hist_demo()
    ct = hist[(hist.centro == "Bilbao") & (hist.turno == "manana")]
    corte = "2026-01"
    prev = backtest_punto(ct, corte, horizonte=6, motor="naive")
    # Debe predecir 6 meses y traer 'real' para los que existan tras el corte.
    assert len(prev) == 6
    assert "real" in prev.columns
    assert prev["real"].notna().any()
    # Entrenó SOLO con <= corte: los periodos previstos son posteriores al corte.
    assert (prev["periodo_objetivo"] > corte).all()


# --------------------------- RECÁLCULO (append-only) ---------------------------
@pytest.fixture()
def entorno_demo(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    import config
    importlib.reload(config)
    for m in ("persistencia.db", "persistencia.historico", "persistencia.previsiones"):
        importlib.reload(importlib.import_module(m))
    import recalcular
    importlib.reload(recalcular)
    return recalcular


def test_recalcular_anade_tanda(entorno_demo):
    recalcular = entorno_demo
    from persistencia import previsiones

    r1 = recalcular.recalcular(modo="prueba", motor="naive", sembrar_demo=True)
    r2 = recalcular.recalcular(modo="prueba", motor="naive")
    assert r1.id_ejecucion is not None and r2.id_ejecucion is not None
    assert r1.id_ejecucion != r2.id_ejecucion
    # Dos tandas coexisten (append-only).
    ejec = previsiones.listar_ejecuciones(modo="prueba")
    assert len(ejec) == 2
