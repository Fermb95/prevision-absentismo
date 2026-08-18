"""
tests/test_demo.py — Pruebas del generador de datos ficticios.

Comprueba: forma correcta, reproducibilidad por semilla, y que el turno de
NOCHE sale con más absentismo que el de mañana (requisito de la sección 4).
"""
from __future__ import annotations

from datetime import date

from config import PARAMS_DEMO
from datos_demo.generador import generar_gripe, generar_panel


FIN = date(2026, 7, 1)  # fecha fija para reproducibilidad del test


def test_forma_del_panel():
    df = generar_panel(FIN)
    # 6 centros × (3 turnos + 'todos') × 18 meses.
    esperado = len(PARAMS_DEMO.centros) * 4 * PARAMS_DEMO.meses_historico
    assert len(df) == esperado
    assert set(df["turno"].unique()) == {"manana", "tarde", "noche", "todos"}
    assert (df["tasa"] > 0).all()
    assert (df["jornadas_perdidas"] <= df["jornadas_teoricas"]).all()


def test_reproducibilidad_por_semilla():
    a = generar_panel(FIN)
    b = generar_panel(FIN)
    # Mismo fin + misma semilla => curva idéntica.
    assert a.equals(b)


def test_noche_peor_que_manana():
    df = generar_panel(FIN)
    media_por_turno = df.groupby("turno")["tasa"].mean()
    assert media_por_turno["noche"] > media_por_turno["manana"]
    assert media_por_turno["tarde"] > media_por_turno["manana"]


def test_pico_de_invierno():
    df = generar_panel(FIN)
    # La tasa media de enero/febrero debe superar a la de mayo/junio.
    invierno = df[df["mes"].isin([1, 2])]["tasa"].mean()
    verano_suave = df[df["mes"].isin([5, 6])]["tasa"].mean()
    assert invierno > verano_suave


def test_gripe_tiene_forma():
    g = generar_gripe(FIN)
    assert list(g.columns) == ["anio", "mes", "incidencia"]
    assert len(g) == PARAMS_DEMO.meses_historico
    # En invierno la incidencia debe ser claramente mayor que en verano.
    inv = g[g["mes"].isin([1, 2])]["incidencia"].mean()
    ver = g[g["mes"].isin([6, 7])]["incidencia"].mean()
    assert inv > ver
