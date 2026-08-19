"""
tests/test_validacion.py — Validación de entrada e ingesta.

La prueba clave (regla innegociable): un fichero con columnas personales debe
ser RECHAZADO. Además: cálculo de tasa, columna 'tasa' alternativa, rangos,
turnos, plantilla descargable y round-trip de FuenteCSV.
"""
from __future__ import annotations

import io

import pandas as pd
import pytest

from ingesta import plantillas
from ingesta.bajas_largas import tratar_bajas_largas
from ingesta.fuente import FuenteAPI, FuenteCSV, cargar_y_validar
from ingesta.validacion import detectar_columnas_personales, validar_absentismo
from config import DefinicionAbsentismo


def _df_valido() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"centro": "Bilbao", "turno": "manana", "anio": 2026, "mes": 1,
             "plantilla_media": 20, "jornadas_teoricas": 400, "jornadas_perdidas": 40},
            {"centro": "Bilbao", "turno": "noche", "anio": 2026, "mes": 1,
             "plantilla_media": 10, "jornadas_teoricas": 200, "jornadas_perdidas": 30},
        ]
    )


# --------------------------- BARRERA DE PRIVACIDAD ---------------------------
@pytest.mark.parametrize(
    "columna",
    ["nombre", "apellidos", "dni", "nif", "id_empleado", "email",
     "edad", "sexo", "genero", "fecha_nacimiento", "nombre_empleado",
     "DNI_trabajador", "Edad"],
)
def test_rechaza_columnas_personales(columna):
    df = _df_valido()
    df[columna] = "x"
    res = validar_absentismo(df)
    assert res.ok is False
    assert columna in res.columnas_personales
    assert any("RECHAZADA" in e for e in res.errores)


def test_no_falsos_positivos_en_columnas_legitimas():
    # Ninguna columna legítima del esquema debe marcarse como personal.
    cols = ["centro", "turno", "anio", "mes", "plantilla_media",
            "jornadas_teoricas", "jornadas_perdidas", "tasa"]
    assert detectar_columnas_personales(cols) == []


# ------------------------------ CÁLCULO DE TASA ------------------------------
def test_calcula_tasa_desde_jornadas():
    res = validar_absentismo(_df_valido())
    assert res.ok
    fila = res.df.iloc[0]
    assert fila["tasa"] == pytest.approx(40 / 400)
    assert fila["periodo"] == "2026-01"


def test_admite_columna_tasa_directa():
    df = pd.DataFrame(
        [{"centro": "Bilbao", "turno": "manana", "anio": 2026, "mes": 3, "tasa": 0.07}]
    )
    res = validar_absentismo(df)
    assert res.ok
    assert res.df.iloc[0]["tasa"] == pytest.approx(0.07)


def test_tasa_en_porcentaje_se_convierte():
    df = pd.DataFrame(
        [{"centro": "Bilbao", "turno": "manana", "anio": 2026, "mes": 3, "tasa": 8.5}]
    )
    res = validar_absentismo(df)
    assert res.ok
    assert res.df.iloc[0]["tasa"] == pytest.approx(0.085)
    assert any("porcentaje" in a for a in res.avisos)


def test_sinonimo_ano_y_acentos():
    df = pd.DataFrame(
        [{"Centro": "Bilbao", "Turno": "Mañana", "año": 2026, "mes": 2, "tasa": 0.05}]
    )
    res = validar_absentismo(df)
    assert res.ok
    assert res.df.iloc[0]["turno"] == "manana"


# ------------------------------ RANGOS / TIPOS ------------------------------
def test_mes_fuera_de_rango():
    df = _df_valido()
    df.loc[0, "mes"] = 13
    res = validar_absentismo(df)
    assert not res.ok


def test_turno_invalido():
    df = _df_valido()
    df.loc[0, "turno"] = "madrugada"
    res = validar_absentismo(df)
    assert not res.ok
    assert any("turno" in e.lower() for e in res.errores)


def test_faltan_columnas_obligatorias():
    df = pd.DataFrame([{"centro": "Bilbao", "anio": 2026, "mes": 1, "tasa": 0.05}])
    res = validar_absentismo(df)
    assert not res.ok


# ------------------------------ BAJAS LARGAS ------------------------------
def _serie_con_outlier() -> pd.DataFrame:
    # 6 meses en torno a 0,06 (mediana 0,06) y un mes atípico de 0,30 (5× mediana).
    filas = [
        {"centro": "X", "turno": "noche", "periodo": f"2026-0{m}", "tasa": t}
        for m, t in zip(range(1, 7), [0.05, 0.06, 0.06, 0.07, 0.06, 0.30])
    ]
    return pd.DataFrame(filas)


def test_topar_winsoriza_el_mes_atipico():
    definicion = DefinicionAbsentismo(tratamiento_bajas_largas="topar", factor_baja_larga=2.5)
    tratado, informe = tratar_bajas_largas(_serie_con_outlier(), definicion)
    assert informe.n_afectadas == 1
    # Mediana = 0,06 → umbral = 0,15. El 0,30 se topa a 0,15; el resto no cambia.
    fila = tratado[tratado["periodo"] == "2026-06"].iloc[0]
    assert fila["tasa"] == pytest.approx(0.06 * 2.5)
    assert fila["tasa_orig"] == pytest.approx(0.30)
    # Un mes normal permanece intacto.
    normal = tratado[tratado["periodo"] == "2026-04"].iloc[0]
    assert normal["tasa"] == pytest.approx(0.07)
    assert not bool(normal["baja_larga"])


def test_marcar_no_cambia_valores():
    definicion = DefinicionAbsentismo(tratamiento_bajas_largas="marcar", factor_baja_larga=2.5)
    tratado, informe = tratar_bajas_largas(_serie_con_outlier(), definicion)
    assert informe.n_afectadas == 1
    fila = tratado[tratado["periodo"] == "2026-06"].iloc[0]
    assert bool(fila["baja_larga"]) is True
    assert fila["tasa"] == pytest.approx(0.30)  # sin cambios


def test_estacionalidad_normal_no_se_topa():
    # Un pico de invierno moderado (1,4× mediana) NO debe considerarse baja larga.
    filas = [
        {"centro": "Y", "turno": "todos", "periodo": f"2026-0{m}", "tasa": t}
        for m, t in zip(range(1, 7), [0.084, 0.06, 0.06, 0.055, 0.06, 0.06])
    ]
    definicion = DefinicionAbsentismo(tratamiento_bajas_largas="topar", factor_baja_larga=2.5)
    tratado, informe = tratar_bajas_largas(pd.DataFrame(filas), definicion)
    assert informe.n_afectadas == 0


# ------------------------------ PLANTILLAS ------------------------------
def test_plantilla_tiene_columnas_exactas():
    df = plantillas.plantilla_absentismo_df()
    from config import COLUMNAS_ABSENTISMO, COLUMNAS_FACTORES
    # Debe contener todas las columnas obligatorias (y además los factores opcionales).
    for c in COLUMNAS_ABSENTISMO:
        assert c in df.columns
    for c in COLUMNAS_FACTORES:
        assert c in df.columns
    # Y la plantilla NO debe contener columnas personales.
    assert detectar_columnas_personales(list(df.columns)) == []


# ------------------------------ FUENTE CSV ------------------------------
def test_fuente_csv_round_trip():
    # Serializamos la plantilla y la volvemos a leer con FuenteCSV.
    csv_bytes = plantillas.plantilla_absentismo_csv()
    buffer = io.BytesIO(csv_bytes)
    buffer.name = "absentismo.csv"
    fuente = FuenteCSV(absentismo=buffer)
    res_abs, res_gripe = cargar_y_validar(fuente)
    assert res_abs.ok
    assert res_abs.n_filas == 3  # plantilla de ejemplo: mañana, tarde y noche
    assert res_gripe is None


def test_fuente_api_es_stub():
    fuente = FuenteAPI(base_url="https://x", token="y")
    with pytest.raises(NotImplementedError):
        fuente.leer_absentismo()
