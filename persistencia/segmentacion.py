"""
persistencia/segmentacion.py — Lectura/escritura de la tabla `segmentacion`.

Detalle del absentismo por centro/turno/PUESTO/mes (agregado por subgrupo, nunca
por persona). Alimenta la página de Segmentación. Se actualiza por upsert.
"""
from __future__ import annotations

import pandas as pd

from persistencia.db import conexion, filas_como_dicts

COLUMNAS: tuple[str, ...] = (
    "centro", "turno", "puesto", "periodo",
    "jornadas_teoricas", "jornadas_perdidas", "plantilla", "carga",
)


def guardar_segmentacion(df: pd.DataFrame, modo: str = "real") -> int:
    """Inserta o actualiza filas de segmentación (upsert por centro+turno+puesto+periodo)."""
    for c in ("centro", "turno", "puesto", "periodo"):
        if c not in df.columns:
            raise ValueError(f"Falta la columna obligatoria '{c}' para guardar segmentación.")

    trabajo = df.copy()
    for c in COLUMNAS:
        if c not in trabajo.columns:
            trabajo[c] = None
    trabajo = trabajo[list(COLUMNAS)].where(pd.notna(trabajo[list(COLUMNAS)]), None)

    sql = """
        INSERT INTO segmentacion
            (centro, turno, puesto, periodo,
             jornadas_teoricas, jornadas_perdidas, plantilla, carga)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(centro, turno, puesto, periodo) DO UPDATE SET
            jornadas_teoricas = excluded.jornadas_teoricas,
            jornadas_perdidas = excluded.jornadas_perdidas,
            plantilla = excluded.plantilla,
            carga = excluded.carga
    """
    n = 0
    with conexion(modo) as con:
        for fila in trabajo.itertuples(index=False, name=None):
            con.execute(sql, tuple(fila))
            n += 1
    return n


def leer_segmentacion(centro: str | None = None, modo: str = "real") -> pd.DataFrame:
    """Lee la segmentación (opcionalmente filtrando por centro)."""
    if centro is None:
        sql, params = f"SELECT {', '.join(COLUMNAS)} FROM segmentacion ORDER BY centro, turno, puesto, periodo", ()
    else:
        sql = f"SELECT {', '.join(COLUMNAS)} FROM segmentacion WHERE centro = ? ORDER BY turno, puesto, periodo"
        params = (centro,)
    with conexion(modo) as con:
        cur = con.execute(sql, tuple(params))
        filas = filas_como_dicts(cur)
    return pd.DataFrame(filas, columns=list(COLUMNAS))


def hay_segmentacion(modo: str = "real") -> bool:
    with conexion(modo) as con:
        cur = con.execute("SELECT 1 FROM segmentacion LIMIT 1")
        return cur.fetchone() is not None
