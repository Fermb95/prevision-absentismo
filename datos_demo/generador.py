"""
datos_demo/generador.py — Generador de datos ficticios realistas (modo prueba).

Genera un panel mensual por centro × turno con:
  * nivel base propio de cada centro,
  * estacionalidad con PICO DE INVIERNO (gripe) y repunte de verano,
  * leve tendencia al alza,
  * ruido aleatorio,
  * turno de NOCHE con más absentismo que el de mañana.

Cada centro usa una SEMILLA propia (semilla_base + índice), de modo que el mismo
centro produce siempre la misma curva (reproducible). No hay ningún dato de
personas: todo es agregado por centro/turno/mes.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from config import PARAMS_DEMO

# Multiplicador estacional por mes (1-12). >1 = más absentismo.
# Pico de invierno (gripe) en dic-ene-feb; repunte de verano en jul-ago.
_ESTACIONALIDAD: dict[int, float] = {
    1: 1.35, 2: 1.30, 3: 1.10, 4: 1.00, 5: 0.95, 6: 0.95,
    7: 1.10, 8: 1.15, 9: 1.00, 10: 1.05, 11: 1.15, 12: 1.30,
}

# Factor por turno: la noche sale sistemáticamente peor que la mañana.
_FACTOR_TURNO: dict[str, float] = {
    "manana": 1.00,
    "tarde": 1.15,
    "noche": 1.40,
}


def _periodos(fin: date, n_meses: int) -> list[tuple[int, int]]:
    """Lista de (anio, mes) de longitud n_meses que TERMINA en `fin` (incluido)."""
    periodos: list[tuple[int, int]] = []
    anio, mes = fin.year, fin.month
    for _ in range(n_meses):
        periodos.append((anio, mes))
        mes -= 1
        if mes == 0:
            mes = 12
            anio -= 1
    return list(reversed(periodos))


def _fin_por_defecto() -> date:
    """Último mes COMPLETO antes de hoy (día 1 del mes anterior al actual)."""
    hoy = date.today()
    if hoy.month == 1:
        return date(hoy.year - 1, 12, 1)
    return date(hoy.year, hoy.month - 1, 1)


def generar_panel(fin: date | None = None) -> pd.DataFrame:
    """Genera el panel completo de datos demo (formato de `absentismo_mensual`).

    Devuelve columnas: centro, turno, anio, mes, plantilla_media,
    jornadas_teoricas, jornadas_perdidas, tasa. Incluye los turnos
    'manana', 'tarde', 'noche' y el agregado 'todos'.
    """
    fin = fin or _fin_por_defecto()
    periodos = _periodos(fin, PARAMS_DEMO.meses_historico)
    filas: list[dict[str, object]] = []

    for idx, centro in enumerate(PARAMS_DEMO.centros):
        rng = np.random.RandomState(PARAMS_DEMO.semilla_base + idx)
        # Nivel base propio del centro (entre ~4% y ~8%).
        base = 0.04 + rng.rand() * 0.04
        # Plantilla base del centro (entre 40 y 160 personas, repartidas por turno).
        plantilla_centro = int(60 + rng.rand() * 100)
        # Pendiente de tendencia leve (0% a +6% acumulado sobre el horizonte).
        pendiente = rng.rand() * 0.06 / max(len(periodos), 1)

        for turno, factor_turno in _FACTOR_TURNO.items():
            # Reparto de plantilla por turno: mañana>tarde>noche.
            reparto = {"manana": 0.45, "tarde": 0.35, "noche": 0.20}[turno]
            plantilla_turno = max(int(plantilla_centro * reparto), 5)

            for t, (anio, mes) in enumerate(periodos):
                estacional = _ESTACIONALIDAD[mes]
                tendencia = 1.0 + pendiente * t
                ruido = 1.0 + rng.normal(0, 0.08)  # ±8% de ruido multiplicativo
                tasa = base * factor_turno * estacional * tendencia * ruido
                tasa = float(np.clip(tasa, 0.005, 0.35))

                # Jornadas teóricas ≈ plantilla × días laborables del mes.
                dias_lab = int(
                    np.busday_count(
                        date(anio, mes, 1),
                        _siguiente_mes(anio, mes),
                    )
                )
                jornadas_teoricas = plantilla_turno * dias_lab
                jornadas_perdidas = int(round(tasa * jornadas_teoricas))

                filas.append(
                    {
                        "centro": centro,
                        "turno": turno,
                        "anio": anio,
                        "mes": mes,
                        "plantilla_media": plantilla_turno,
                        "jornadas_teoricas": jornadas_teoricas,
                        "jornadas_perdidas": jornadas_perdidas,
                        "tasa": round(tasa, 5),
                    }
                )

    df = pd.DataFrame(filas)
    df = _anadir_turno_todos(df)
    return df.sort_values(["centro", "turno", "anio", "mes"]).reset_index(drop=True)


def _siguiente_mes(anio: int, mes: int) -> date:
    """Primer día del mes siguiente (para contar días laborables del mes)."""
    return date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)


def _anadir_turno_todos(df: pd.DataFrame) -> pd.DataFrame:
    """Añade el turno agregado 'todos' sumando los tres turnos por centro/mes."""
    agg = (
        df.groupby(["centro", "anio", "mes"], as_index=False)
        .agg(
            plantilla_media=("plantilla_media", "sum"),
            jornadas_teoricas=("jornadas_teoricas", "sum"),
            jornadas_perdidas=("jornadas_perdidas", "sum"),
        )
    )
    agg["turno"] = "todos"
    agg["tasa"] = (agg["jornadas_perdidas"] / agg["jornadas_teoricas"]).round(5)
    return pd.concat([df, agg], ignore_index=True)


def generar_gripe(fin: date | None = None) -> pd.DataFrame:
    """Genera la curva de incidencia de gripe demo (regresor externo opcional).

    Columnas: anio, mes, incidencia (casos por 100.000 hab., aprox.). Correlaciona
    con el invierno para que el modelo pueda usarla como regresor.
    """
    fin = fin or _fin_por_defecto()
    periodos = _periodos(fin, PARAMS_DEMO.meses_historico)
    rng = np.random.RandomState(PARAMS_DEMO.semilla_base - 1)
    filas: list[dict[str, object]] = []
    for anio, mes in periodos:
        # Incidencia alta en invierno, casi nula en verano.
        pico = _ESTACIONALIDAD[mes] - 0.95  # 0 en verano suave, ~0.4 en invierno
        incidencia = max(0.0, pico * 700 + rng.normal(0, 30))
        filas.append({"anio": anio, "mes": mes, "incidencia": round(incidencia, 1)})
    return pd.DataFrame(filas)


def generar_historico_para_db(fin: date | None = None) -> pd.DataFrame:
    """Panel demo en el ESQUEMA de la tabla `historico` (para persistir).

    Columnas: centro, turno, periodo ('YYYY-MM'), tasa, jornadas_perdidas, plantilla.
    """
    df = generar_panel(fin)
    df["periodo"] = (
        df["anio"].astype(str) + "-" + df["mes"].astype(str).str.zfill(2)
    )
    return df[
        ["centro", "turno", "periodo", "tasa", "jornadas_perdidas", "plantilla_media"]
    ].rename(columns={"plantilla_media": "plantilla"})
