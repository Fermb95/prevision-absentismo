"""
modelo/factores.py — Análisis de factores estructurales (nivel centro/turno).

Los factores explican diferencias ENTRE centros/turnos (análisis transversal), no
predicen la evolución temporal de una serie. Aquí:
  * `tabla_factores_absentismo`: une el absentismo medio de cada centro/turno con
    sus factores.
  * `comparar_flexibilidad_rotacion`: absentismo medio por tipo de horario.
  * `ranking_factores`: qué factor numérico se asocia más (correlación) con el
    absentismo, con una nota honesta sobre correlación ≠ causalidad.

IMPORTANTE: solo factores AGREGADOS del centro/turno. Nunca datos de personas ni
características protegidas (sexo, edad, discapacidad, afiliación sindical).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config

_FACTORES_NUM = ("rotacion_pct", "antiguedad_media", "satisfaccion_media", "jornada_media")

# Nombres legibles para la interfaz.
NOMBRE_FACTOR = {
    "tipo_horario": "Tipo de horario",
    "rotacion_pct": "Rotación (%)",
    "antiguedad_media": "Antigüedad media (años)",
    "satisfaccion_media": "Satisfacción media",
    "jornada_media": "Jornada media (h)",
}


def tabla_factores_absentismo(
    historico_df: pd.DataFrame, factores_df: pd.DataFrame
) -> pd.DataFrame:
    """Une el absentismo medio de cada centro/turno con sus factores.

    Devuelve una fila por centro×turno con: centro, turno, tasa_media y los
    factores (los numéricos promediados; el tipo de horario, el más frecuente).
    """
    if historico_df.empty or factores_df.empty:
        return pd.DataFrame()

    tasa = (
        historico_df.groupby(["centro", "turno"], as_index=False)["tasa"]
        .mean().rename(columns={"tasa": "tasa_media"})
    )

    agg = {c: "mean" for c in _FACTORES_NUM if c in factores_df.columns}
    fac_num = factores_df.groupby(["centro", "turno"], as_index=False).agg(agg)

    # tipo_horario: el valor más frecuente por centro/turno.
    if "tipo_horario" in factores_df.columns:
        tipo = (
            factores_df.dropna(subset=["tipo_horario"])
            .groupby(["centro", "turno"])["tipo_horario"]
            .agg(lambda s: s.value_counts().idxmax())
            .reset_index()
        )
        fac = fac_num.merge(tipo, on=["centro", "turno"], how="outer")
    else:
        fac = fac_num

    return tasa.merge(fac, on=["centro", "turno"], how="inner")


def comparar_flexibilidad_rotacion(tabla: pd.DataFrame) -> pd.DataFrame:
    """Absentismo medio por tipo de horario (flexible/fijo/rotativo)."""
    if tabla.empty or "tipo_horario" not in tabla.columns:
        return pd.DataFrame(columns=["tipo_horario", "tasa_media", "n"])
    out = (
        tabla.dropna(subset=["tipo_horario"])
        .groupby("tipo_horario")
        .agg(tasa_media=("tasa_media", "mean"), n=("tasa_media", "size"))
        .reset_index()
        .sort_values("tasa_media", ascending=False)
    )
    return out


def ranking_factores(tabla: pd.DataFrame) -> pd.DataFrame:
    """Correlación (Pearson) de cada factor numérico con la tasa media.

    Devuelve columnas: factor, nombre, correlacion, n. Ordenado por |correlación|.
    Correlación positiva = a más factor, más absentismo. Requiere ≥3 puntos.
    """
    filas: list[dict[str, object]] = []
    for c in _FACTORES_NUM:
        if c not in tabla.columns:
            continue
        sub = tabla[["tasa_media", c]].dropna()
        if len(sub) < 3 or sub[c].nunique() < 2:
            corr = float("nan")
        else:
            corr = float(np.corrcoef(sub[c], sub["tasa_media"])[0, 1])
        filas.append({
            "factor": c, "nombre": NOMBRE_FACTOR.get(c, c),
            "correlacion": corr, "n": len(sub),
        })
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    return df.reindex(df["correlacion"].abs().sort_values(ascending=False).index).reset_index(drop=True)
