"""
tests/test_mejoras.py — Dimensionamiento de plantilla, semáforo y exportación.
"""
from __future__ import annotations

import io

import pandas as pd
import pytest

from ui import servicios


# ------------------------------ SEMÁFORO ------------------------------
@pytest.mark.parametrize(
    "tasa,nivel",
    [(0.03, "verde"), (0.059, "verde"), (0.06, "ambar"), (0.10, "ambar"),
     (0.1001, "rojo"), (0.25, "rojo")],
)
def test_clasificar_semaforo(tasa, nivel):
    emoji, n = servicios.clasificar_semaforo(tasa)
    assert n == nivel
    assert emoji in ("🟢", "🟡", "🔴")


def test_semaforo_sin_dato():
    emoji, nivel = servicios.clasificar_semaforo(float("nan"))
    assert nivel == "sin dato"


# --------------------------- DIMENSIONAMIENTO ---------------------------
def test_fte_ausentes():
    assert servicios.fte_ausentes(0.10, 30) == pytest.approx(3.0)


def test_refuerzo_redondea_arriba():
    # 0,085 × 30 = 2,55 → refuerzo = 3 personas.
    assert servicios.refuerzo_recomendado(0.085, 30) == 3


def test_plantilla_ref_toma_la_ultima():
    hist = pd.DataFrame([
        {"periodo": "2026-01", "plantilla": 20},
        {"periodo": "2026-03", "plantilla": 25},
        {"periodo": "2026-02", "plantilla": 22},
    ])
    assert servicios.plantilla_ref(hist) == 25.0


def test_fiabilidad_por_meses():
    pocos = pd.DataFrame({"periodo": [f"2026-0{m}" for m in range(1, 6)]})
    muchos = pd.DataFrame({"periodo": [f"2025-{m:02d}" for m in range(1, 13)] + ["2026-01"]})
    assert servicios.fiabilidad_de(pocos) == "baja"
    assert servicios.fiabilidad_de(muchos) == "alta"


# ------------------------------ EXPORTACIÓN ------------------------------
def test_construir_excel_legible():
    df1 = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    df2 = pd.DataFrame({"x": [9]})
    data = servicios.construir_excel({"prevision": df1, "historico": df2})
    assert isinstance(data, bytes) and len(data) > 0
    # Se puede volver a leer y las hojas existen.
    xls = pd.read_excel(io.BytesIO(data), sheet_name=None)
    assert set(xls.keys()) == {"prevision", "historico"}
    assert list(xls["prevision"].columns) == ["a", "b"]


def test_csv_bytes_tiene_cabecera():
    df = pd.DataFrame({"centro": ["X"], "tasa": [0.07]})
    data = servicios.a_csv_bytes(df)
    texto = data.decode("utf-8-sig")
    assert "centro;tasa" in texto


# ------------------------------ ESPAÑOL ------------------------------
def test_turno_bonito_con_enie():
    import config
    assert servicios.turno_bonito("manana") == "Mañana"
    assert servicios.turno_bonito("noche") == "Noche"
    # Todos los turnos válidos deben tener etiqueta en español (sin 'manana').
    for t in config.TURNOS_VALIDOS:
        etiqueta = servicios.turno_bonito(t)
        assert etiqueta[0].isupper()
        assert "manana" not in etiqueta
