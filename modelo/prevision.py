"""
modelo/prevision.py — Orquestación de la previsión.

Ajusta UN modelo por cada combinación centro × turno (segmentado), aplica
degradación elegante (si hay poco histórico usa el motor naive y avisa de baja
fiabilidad, en vez de romper), usa la gripe como regresor si se aporta, y
devuelve una tabla con el esquema de la tabla `previsiones`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from config import PARAMS_MODELO
from modelo.motor import (
    crear_modelo,
    motor_disponible,
    periodo_a_ts,
    serie_mensual,
    siguientes_periodos,
)


@dataclass
class ResultadoPrevision:
    previsiones: pd.DataFrame            # centro,turno,periodo_objetivo,valor,lo,hi,modelo
    detalle: pd.DataFrame               # centro,turno,n_meses,fiabilidad,modelo_usado
    avisos: list[str] = field(default_factory=list)


def _serie_gripe(gripe_df: pd.DataFrame | None) -> pd.Series | None:
    """Convierte el fichero de gripe (anio,mes,incidencia) en Serie mensual."""
    if gripe_df is None or gripe_df.empty:
        return None
    g = gripe_df.copy()
    idx = [periodo_a_ts(f"{int(a)}-{int(m):02d}") for a, m in zip(g["anio"], g["mes"])]
    return pd.Series(g["incidencia"].to_numpy(float), index=pd.DatetimeIndex(idx)).sort_index()


def _elegir_motor(nombre_pedido: str, n_meses: int) -> tuple[str, str | None]:
    """Decide qué motor usar y devuelve (motor_efectivo, aviso|None)."""
    # Con muy poco histórico, forzamos naive (degradación elegante).
    if n_meses < PARAMS_MODELO.min_meses_para_ajustar:
        return "naive", (
            f"solo {n_meses} meses de histórico: se usa un modelo simple (naive) "
            "y la fiabilidad es BAJA"
        )
    if nombre_pedido != "naive" and not motor_disponible(nombre_pedido):
        return "naive", (
            f"el motor '{nombre_pedido}' no está disponible en este entorno; "
            "se usa 'naive' como alternativa"
        )
    return nombre_pedido, None


def calcular_prevision(
    historico_df: pd.DataFrame,
    motor: str = PARAMS_MODELO.motor_por_defecto,
    horizonte: int = max(PARAMS_MODELO.horizontes_meses),
    gripe_df: pd.DataFrame | None = None,
) -> ResultadoPrevision:
    """Calcula la previsión para todas las combinaciones centro × turno.

    historico_df: columnas al menos 'centro','turno','periodo','tasa'.
    Devuelve un ResultadoPrevision con la tabla lista para persistir.
    """
    gripe = _serie_gripe(gripe_df)
    filas_prev: list[pd.DataFrame] = []
    filas_detalle: list[dict[str, object]] = []
    avisos: list[str] = []

    for (centro, turno), sub in historico_df.groupby(["centro", "turno"]):
        serie = serie_mensual(sub)
        n = len(serie)
        if n == 0:
            continue

        motor_ef, aviso = _elegir_motor(motor, n)
        if aviso:
            avisos.append(f"{centro}/{turno}: {aviso}.")

        periodos = siguientes_periodos(serie.index[-1].strftime("%Y-%m"), horizonte)

        try:
            modelo = crear_modelo(motor_ef)
            modelo.ajustar(serie, gripe=gripe)
            prev = modelo.prever(periodos, gripe_futura=gripe)
        except Exception as exc:  # degradación elegante ante cualquier fallo del motor
            avisos.append(
                f"{centro}/{turno}: el motor '{motor_ef}' falló ({exc}); "
                "se usa 'naive'."
            )
            modelo = crear_modelo("naive")
            modelo.ajustar(serie)
            prev = modelo.prever(periodos)
            motor_ef = "naive"

        prev.insert(0, "turno", turno)
        prev.insert(0, "centro", centro)
        prev["modelo"] = motor_ef
        filas_prev.append(prev)

        fiabilidad = "alta" if n >= PARAMS_MODELO.min_meses_fiable else "baja"
        filas_detalle.append(
            {"centro": centro, "turno": turno, "n_meses": n,
             "fiabilidad": fiabilidad, "modelo_usado": motor_ef}
        )

    previsiones = (
        pd.concat(filas_prev, ignore_index=True)
        if filas_prev
        else pd.DataFrame(
            columns=["centro", "turno", "periodo_objetivo", "valor", "lo", "hi", "modelo"]
        )
    )
    detalle = pd.DataFrame(filas_detalle)
    return ResultadoPrevision(previsiones=previsiones, detalle=detalle, avisos=avisos)
