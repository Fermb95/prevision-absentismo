"""
modelo/segmentacion.py — Análisis de micro-segmentación dentro de un centro.

Trabaja con subgrupos AGREGADOS (turno × puesto), nunca con personas. Ofrece:
  * `tabla_segmentos`: absentismo por subgrupo (tasa ponderada, jornadas perdidas
    al mes, plantilla, carga media).
  * `anadir_franjas_carga`: clasifica cada subgrupo en franja de carga (terciles).
  * `por_dimension`: absentismo ponderado por turno, por puesto o por franja.
  * `focos`: subgrupos priorizados por IMPACTO (jornadas perdidas al mes).
  * `carga_vs_absentismo`: correlación entre carga y absentismo entre subgrupos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config


def tabla_segmentos(seg_df: pd.DataFrame, centro: str | None = None) -> pd.DataFrame:
    """Absentismo por subgrupo (centro, turno, puesto), agregando los meses.

    Columnas: centro, turno, puesto, tasa_media, jornadas_perdidas_mes, plantilla,
    carga_media, n_meses (+ perdidas_tot, teoricas_tot para reagrupar).
    """
    if seg_df is None or seg_df.empty:
        return pd.DataFrame()
    df = seg_df.copy()
    if centro is not None:
        df = df[df["centro"] == centro]
    if df.empty:
        return pd.DataFrame()

    for c in ("jornadas_teoricas", "jornadas_perdidas", "plantilla", "carga"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    filas: list[dict[str, object]] = []
    for (ce, tu, pu), g in df.groupby(["centro", "turno", "puesto"]):
        teoricas = float(g["jornadas_teoricas"].sum())
        perdidas = float(g["jornadas_perdidas"].sum())
        n_meses = int(g["periodo"].nunique())
        tasa = perdidas / teoricas if teoricas > 0 else float("nan")
        filas.append({
            "centro": ce, "turno": tu, "puesto": pu,
            "tasa_media": tasa,
            "jornadas_perdidas_mes": perdidas / n_meses if n_meses else float("nan"),
            "plantilla": float(g["plantilla"].mean()),
            "carga_media": float(g["carga"].mean()),
            "n_meses": n_meses,
            "perdidas_tot": perdidas, "teoricas_tot": teoricas,
        })
    return pd.DataFrame(filas)


def anadir_franjas_carga(tabla: pd.DataFrame) -> pd.DataFrame:
    """Añade la columna 'franja' (baja/media/alta) por terciles de carga_media."""
    out = tabla.copy()
    if out.empty or out["carga_media"].notna().sum() < 3:
        out["franja"] = pd.NA
        return out
    try:
        out["franja"] = pd.qcut(
            out["carga_media"], q=3, labels=list(config.FRANJAS_CARGA), duplicates="drop"
        )
    except ValueError:
        out["franja"] = pd.NA
    return out


def por_dimension(tabla: pd.DataFrame, dimension: str) -> pd.DataFrame:
    """Absentismo ponderado por una dimensión ('turno', 'puesto' o 'franja')."""
    if tabla.empty or dimension not in tabla.columns:
        return pd.DataFrame(columns=[dimension, "tasa_media", "jornadas_perdidas_mes", "n"])
    g = tabla.dropna(subset=[dimension]).groupby(dimension, observed=True)
    out = g.apply(
        lambda x: pd.Series({
            "tasa_media": x["perdidas_tot"].sum() / x["teoricas_tot"].sum()
            if x["teoricas_tot"].sum() > 0 else float("nan"),
            "jornadas_perdidas_mes": x["jornadas_perdidas_mes"].sum(),
            "n": len(x),
        }),
        include_groups=False,
    ).reset_index()
    return out.sort_values("tasa_media", ascending=False)


def focos(tabla: pd.DataFrame, min_plantilla: float = 0, top: int = 8) -> pd.DataFrame:
    """Subgrupos priorizados por IMPACTO (jornadas perdidas al mes).

    Un 5% en un grupo grande pierde más días que un 15% en uno diminuto: por eso
    se prioriza por jornadas perdidas al mes, mostrando también la tasa.
    """
    if tabla.empty:
        return tabla
    t = tabla[tabla["plantilla"] >= min_plantilla].copy()
    return t.sort_values("jornadas_perdidas_mes", ascending=False).head(top)


def carga_vs_absentismo(tabla: pd.DataFrame) -> float:
    """Correlación (Pearson) entre carga media y tasa entre subgrupos. NaN si <3."""
    sub = tabla[["carga_media", "tasa_media"]].dropna()
    if len(sub) < 3 or sub["carga_media"].nunique() < 2:
        return float("nan")
    return float(np.corrcoef(sub["carga_media"], sub["tasa_media"])[0, 1])
