"""
persistencia/previsiones.py — Tabla de previsiones VERSIONADAS (append-only).

REGLA INNEGOCIABLE (sección 7): esta tabla NUNCA se sobrescribe. Cada recálculo
crea una nueva `id_ejecucion` con su `fecha_calculo` y AÑADE filas. Así se
conserva el histórico completo de "qué predijimos y cuándo".

Por diseño, este módulo NO expone ninguna función de UPDATE ni DELETE sobre
`previsiones`. Solo INSERT (guardar_tanda) y SELECT (lecturas).
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pandas as pd

from persistencia.db import conexion, filas_como_dicts

COLUMNAS: tuple[str, ...] = (
    "id_ejecucion", "fecha_calculo", "centro", "turno",
    "periodo_objetivo", "valor", "lo", "hi", "modelo",
)


def nueva_id_ejecucion() -> str:
    """Genera un identificador único para una tanda de recálculo."""
    return uuid.uuid4().hex


def guardar_tanda(
    df: pd.DataFrame,
    id_ejecucion: str,
    fecha_calculo: datetime | None = None,
    modo: str = "real",
) -> int:
    """Añade una tanda de previsiones (INSERT, nunca sobrescribe).

    El DataFrame debe traer: centro, turno, periodo_objetivo, valor, lo, hi, modelo.
    id_ejecucion y fecha_calculo se aplican a todas las filas de la tanda.
    Devuelve el nº de filas insertadas.
    """
    requeridas = ("centro", "turno", "periodo_objetivo", "valor", "lo", "hi", "modelo")
    faltan = [c for c in requeridas if c not in df.columns]
    if faltan:
        raise ValueError(f"Faltan columnas en la tanda de previsiones: {faltan}")

    fecha = (fecha_calculo or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    sql = """
        INSERT INTO previsiones
            (id_ejecucion, fecha_calculo, centro, turno,
             periodo_objetivo, valor, lo, hi, modelo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    n = 0
    with conexion(modo) as con:
        for _, r in df.iterrows():
            con.execute(
                sql,
                (
                    id_ejecucion, fecha, r["centro"], r["turno"],
                    r["periodo_objetivo"], float(r["valor"]),
                    float(r["lo"]), float(r["hi"]), r["modelo"],
                ),
            )
            n += 1
    return n


def leer_tanda(id_ejecucion: str, modo: str = "real") -> pd.DataFrame:
    """Lee todas las filas de una tanda concreta."""
    with conexion(modo) as con:
        cur = con.execute(
            f"SELECT {', '.join(COLUMNAS)} FROM previsiones "
            "WHERE id_ejecucion = ? ORDER BY centro, turno, periodo_objetivo",
            (id_ejecucion,),
        )
        filas = filas_como_dicts(cur)
    return pd.DataFrame(filas, columns=list(COLUMNAS))


def listar_ejecuciones(modo: str = "real") -> pd.DataFrame:
    """Devuelve las tandas existentes (id, fecha, modelo, nº filas), recientes primero."""
    sql = """
        SELECT id_ejecucion,
               MIN(fecha_calculo) AS fecha_calculo,
               MIN(modelo)        AS modelo,
               COUNT(*)           AS n_filas
        FROM previsiones
        GROUP BY id_ejecucion
        ORDER BY fecha_calculo DESC
    """
    with conexion(modo) as con:
        cur = con.execute(sql)
        filas = filas_como_dicts(cur)
    return pd.DataFrame(filas, columns=["id_ejecucion", "fecha_calculo", "modelo", "n_filas"])


def leer_prevision_a_fecha(
    fecha_analisis: datetime,
    centro: str | None = None,
    turno: str | None = None,
    modo: str = "real",
) -> pd.DataFrame:
    """Lee la previsión GUARDADA vigente a una fecha dada (no recalcula al vuelo).

    Toma la tanda más reciente cuya `fecha_calculo` <= fecha_analisis. Así se
    responde a "¿qué preveíamos a fecha X?" leyendo lo ya persistido (sección 7).
    Devuelve DataFrame vacío si no hay ninguna tanda anterior a esa fecha.
    """
    tope = fecha_analisis.strftime("%Y-%m-%d %H:%M:%S")
    with conexion(modo) as con:
        cur = con.execute(
            "SELECT id_ejecucion FROM previsiones WHERE fecha_calculo <= ? "
            "ORDER BY fecha_calculo DESC LIMIT 1",
            (tope,),
        )
        fila = cur.fetchone()
        if fila is None:
            return pd.DataFrame(columns=list(COLUMNAS))
        id_ej = fila[0]

        clausulas = ["id_ejecucion = ?"]
        params: list[object] = [id_ej]
        if centro is not None:
            clausulas.append("centro = ?")
            params.append(centro)
        if turno is not None:
            clausulas.append("turno = ?")
            params.append(turno)
        where = " AND ".join(clausulas)
        cur = con.execute(
            f"SELECT {', '.join(COLUMNAS)} FROM previsiones WHERE {where} "
            "ORDER BY periodo_objetivo",
            tuple(params),
        )
        filas = filas_como_dicts(cur)
    return pd.DataFrame(filas, columns=list(COLUMNAS))


def leer_ultima_prevision(
    centro: str | None = None,
    turno: str | None = None,
    modo: str = "real",
) -> pd.DataFrame:
    """Atajo: la previsión de la tanda más reciente que exista."""
    return leer_prevision_a_fecha(datetime.now(), centro=centro, turno=turno, modo=modo)
