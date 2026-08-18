"""
persistencia/historico.py — Lectura/escritura de la tabla `historico`.

El histórico es el dato OBSERVADO (agregado por centro/turno/mes). A diferencia
de las previsiones, aquí SÍ se puede sobrescribir: si se recargan datos de un
mes, se actualiza la fila (upsert por centro+turno+periodo).

Todas las funciones aceptan `modo` ('real' | 'prueba') para trabajar sobre la
base correspondiente (ver persistencia/db.py).
"""
from __future__ import annotations

import pandas as pd

from persistencia.db import conexion, filas_como_dicts

# Columnas canónicas de la tabla histórico.
COLUMNAS: tuple[str, ...] = (
    "centro", "turno", "periodo", "tasa", "jornadas_perdidas", "plantilla",
)


def guardar_historico(df: pd.DataFrame, modo: str = "real") -> int:
    """Inserta o actualiza filas de histórico (upsert por centro+turno+periodo).

    Se espera un DataFrame con las columnas de COLUMNAS. Devuelve nº de filas escritas.
    """
    faltan = [c for c in COLUMNAS if c not in df.columns]
    if faltan:
        raise ValueError(f"Faltan columnas en el histórico a guardar: {faltan}")

    filas = df[list(COLUMNAS)].itertuples(index=False, name=None)
    sql = """
        INSERT INTO historico (centro, turno, periodo, tasa, jornadas_perdidas, plantilla)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(centro, turno, periodo) DO UPDATE SET
            tasa = excluded.tasa,
            jornadas_perdidas = excluded.jornadas_perdidas,
            plantilla = excluded.plantilla
    """
    n = 0
    with conexion(modo) as con:
        for fila in filas:
            con.execute(sql, fila)
            n += 1
    return n


def leer_historico(
    centro: str | None = None,
    turno: str | None = None,
    hasta_periodo: str | None = None,
    modo: str = "real",
) -> pd.DataFrame:
    """Lee el histórico, con filtros opcionales.

    hasta_periodo ('YYYY-MM'): devuelve solo periodos <= ese valor. Útil para el
    backtest ("ponte a fecha X usando solo lo que se sabía entonces").
    """
    clausulas: list[str] = []
    params: list[object] = []
    if centro is not None:
        clausulas.append("centro = ?")
        params.append(centro)
    if turno is not None:
        clausulas.append("turno = ?")
        params.append(turno)
    if hasta_periodo is not None:
        clausulas.append("periodo <= ?")
        params.append(hasta_periodo)

    where = f"WHERE {' AND '.join(clausulas)}" if clausulas else ""
    sql = f"SELECT {', '.join(COLUMNAS)} FROM historico {where} ORDER BY centro, turno, periodo"

    with conexion(modo) as con:
        cur = con.execute(sql, params)
        filas = filas_como_dicts(cur)
    return pd.DataFrame(filas, columns=list(COLUMNAS))


def listar_centros(modo: str = "real") -> list[str]:
    """Devuelve los centros presentes en el histórico, ordenados."""
    with conexion(modo) as con:
        cur = con.execute("SELECT DISTINCT centro FROM historico ORDER BY centro")
        return [fila[0] for fila in cur.fetchall()]


def listar_turnos(centro: str | None = None, modo: str = "real") -> list[str]:
    """Devuelve los turnos presentes (opcionalmente filtrando por centro)."""
    if centro is None:
        sql, params = "SELECT DISTINCT turno FROM historico ORDER BY turno", []
    else:
        sql, params = (
            "SELECT DISTINCT turno FROM historico WHERE centro = ? ORDER BY turno",
            [centro],
        )
    with conexion(modo) as con:
        cur = con.execute(sql, params)
        return [fila[0] for fila in cur.fetchall()]


def vaciar_historico(modo: str = "real") -> None:
    """Borra TODO el histórico (usado al recargar datos reales desde cero)."""
    with conexion(modo) as con:
        con.execute("DELETE FROM historico")
