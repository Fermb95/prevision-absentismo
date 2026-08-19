"""
persistencia/factores.py — Lectura/escritura de la tabla `factores`.

Factores estructurales AGREGADOS por centro/turno/mes (tipo de horario,
rotación, antigüedad media, satisfacción media, jornada media). Son propiedades
del centro/turno, nunca de personas. Se actualizan por upsert como el histórico.
"""
from __future__ import annotations

import pandas as pd

from persistencia.db import conexion, filas_como_dicts

COLUMNAS: tuple[str, ...] = (
    "centro", "turno", "periodo", "tipo_horario", "rotacion_pct",
    "antiguedad_media", "satisfaccion_media", "jornada_media",
)


def guardar_factores(df: pd.DataFrame, modo: str = "real") -> int:
    """Inserta o actualiza factores (upsert por centro+turno+periodo).

    Acepta un DataFrame que contenga 'centro','turno','periodo' y una o varias de
    las columnas de factor; las que falten se guardan como NULL. Devuelve nº filas.
    """
    for c in ("centro", "turno", "periodo"):
        if c not in df.columns:
            raise ValueError(f"Falta la columna obligatoria '{c}' para guardar factores.")

    trabajo = df.copy()
    for c in COLUMNAS:
        if c not in trabajo.columns:
            trabajo[c] = None
    trabajo = trabajo[list(COLUMNAS)].where(pd.notna(trabajo[list(COLUMNAS)]), None)

    sql = """
        INSERT INTO factores
            (centro, turno, periodo, tipo_horario, rotacion_pct,
             antiguedad_media, satisfaccion_media, jornada_media)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(centro, turno, periodo) DO UPDATE SET
            tipo_horario = excluded.tipo_horario,
            rotacion_pct = excluded.rotacion_pct,
            antiguedad_media = excluded.antiguedad_media,
            satisfaccion_media = excluded.satisfaccion_media,
            jornada_media = excluded.jornada_media
    """
    n = 0
    with conexion(modo) as con:
        for fila in trabajo.itertuples(index=False, name=None):
            con.execute(sql, fila)
            n += 1
    return n


def leer_factores(
    centro: str | None = None,
    turno: str | None = None,
    modo: str = "real",
) -> pd.DataFrame:
    """Lee los factores (con filtros opcionales)."""
    clausulas: list[str] = []
    params: list[object] = []
    if centro is not None:
        clausulas.append("centro = ?")
        params.append(centro)
    if turno is not None:
        clausulas.append("turno = ?")
        params.append(turno)
    where = f"WHERE {' AND '.join(clausulas)}" if clausulas else ""
    sql = f"SELECT {', '.join(COLUMNAS)} FROM factores {where} ORDER BY centro, turno, periodo"
    with conexion(modo) as con:
        cur = con.execute(sql, tuple(params))
        filas = filas_como_dicts(cur)
    return pd.DataFrame(filas, columns=list(COLUMNAS))


def hay_factores(modo: str = "real") -> bool:
    """True si existe al menos una fila de factores en el modo dado."""
    with conexion(modo) as con:
        cur = con.execute("SELECT 1 FROM factores LIMIT 1")
        return cur.fetchone() is not None
