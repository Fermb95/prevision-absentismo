"""
ingesta/segmentacion.py — Prepara los datos validados para persistir.

Si el fichero trae la columna 'puesto', hay detalle por centro/turno/PUESTO. En
ese caso se separa en dos:
  * `segmentacion`: el detalle por subgrupo (para la página de Segmentación).
  * `historico`: agregado a centro/turno (para la previsión), sumando jornadas.

Si no hay 'puesto', el histórico se construye directamente (comportamiento previo)
y la segmentación queda vacía.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config

_HIST_COLS = ["centro", "turno", "periodo", "tasa", "jornadas_perdidas", "plantilla"]


def preparar_persistencia(res_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (historico_df, segmentacion_df) a partir del DataFrame validado."""
    df = res_df.copy()

    if config.COLUMNA_PUESTO not in df.columns:
        hist = df.rename(columns={"plantilla_media": "plantilla"})
        for c in _HIST_COLS:
            if c not in hist.columns:
                hist[c] = pd.NA
        return hist[_HIST_COLS], pd.DataFrame()

    # --- Con puesto: detalle + agregado ---
    seg = df.rename(columns={"plantilla_media": "plantilla"})
    for c in ("jornadas_teoricas", "jornadas_perdidas", "plantilla", config.COLUMNA_CARGA):
        if c not in seg.columns:
            seg[c] = pd.NA
    seg_cols = ["centro", "turno", "puesto", "periodo",
                "jornadas_teoricas", "jornadas_perdidas", "plantilla", config.COLUMNA_CARGA]
    segmentacion_df = seg[seg_cols].rename(columns={config.COLUMNA_CARGA: "carga"})

    hist = _agregar_historico(df)
    return hist, segmentacion_df


def _agregar_historico(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega el detalle por puesto a centro/turno/periodo para la previsión."""
    d = df.copy()
    tiene_teoricas = "jornadas_teoricas" in d.columns and d["jornadas_teoricas"].notna().any()
    tiene_plantilla = "plantilla_media" in d.columns and d["plantilla_media"].notna().any()

    filas: list[dict[str, object]] = []
    for (centro, turno, periodo), g in d.groupby(["centro", "turno", "periodo"]):
        perdidas = pd.to_numeric(g.get("jornadas_perdidas"), errors="coerce")
        teoricas = pd.to_numeric(g.get("jornadas_teoricas"), errors="coerce")
        plantilla = pd.to_numeric(g.get("plantilla_media"), errors="coerce")

        if tiene_teoricas and teoricas.sum() > 0:
            tasa = float(perdidas.sum() / teoricas.sum())
        elif tiene_plantilla and plantilla.sum() > 0:
            tasa = float((g["tasa"] * plantilla).sum() / plantilla.sum())
        else:
            tasa = float(g["tasa"].mean())

        filas.append({
            "centro": centro, "turno": turno, "periodo": periodo,
            "tasa": round(tasa, 6),
            "jornadas_perdidas": int(perdidas.sum()) if perdidas.notna().any() else None,
            "plantilla": int(plantilla.sum()) if plantilla.notna().any() else None,
        })
    return pd.DataFrame(filas, columns=_HIST_COLS)
