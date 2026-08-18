"""
modelo/metricas.py — Métricas de error para la página de Precisión.

  * MAPE  — error porcentual absoluto medio (¿cuánto nos equivocamos?).
  * Sesgo — error medio con signo (¿tendemos a quedarnos CORTOS o LARGOS?).
  * Alerta de deriva — si el modelo lleva varios meses desviándose por encima
    de un umbral (config.UMBRALES_ALERTA), avisa de que se está deteriorando.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from config import UMBRALES_ALERTA


@dataclass
class ResumenError:
    n: int
    mape: float           # %
    sesgo: float          # error medio con signo (en tasa; + = nos pasamos)
    sesgo_relativo: float  # % medio con signo respecto a lo real
    interpretacion: str


def _alinea(real: pd.Series, pred: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Alinea real y previsión por índice común y descarta NaN."""
    df = pd.concat([real.rename("real"), pred.rename("pred")], axis=1).dropna()
    return df["real"].to_numpy(float), df["pred"].to_numpy(float)


def mape(real: pd.Series, pred: pd.Series) -> float:
    """MAPE en % (ignora meses con real=0 para no dividir por cero)."""
    r, p = _alinea(real, pred)
    mask = r != 0
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs((r[mask] - p[mask]) / r[mask])) * 100.0)


def sesgo(real: pd.Series, pred: pd.Series) -> float:
    """Error medio con signo (pred - real). Positivo = nos pasamos (largos)."""
    r, p = _alinea(real, pred)
    if len(r) == 0:
        return float("nan")
    return float(np.mean(p - r))


def sesgo_relativo(real: pd.Series, pred: pd.Series) -> float:
    """Sesgo relativo medio en % respecto a lo real (ignora real=0)."""
    r, p = _alinea(real, pred)
    mask = r != 0
    if not mask.any():
        return float("nan")
    return float(np.mean((p[mask] - r[mask]) / r[mask]) * 100.0)


def resumen_error(real: pd.Series, pred: pd.Series) -> ResumenError:
    """Calcula todas las métricas y una interpretación en lenguaje natural."""
    r, p = _alinea(real, pred)
    n = len(r)
    if n == 0:
        return ResumenError(0, float("nan"), float("nan"), float("nan"),
                            "No hay meses solapados para comparar.")
    m = mape(real, pred)
    s = sesgo(real, pred)
    sr = sesgo_relativo(real, pred)
    if abs(sr) < 3:
        tendencia = "sin sesgo apreciable"
    elif sr > 0:
        tendencia = "tendemos a quedarnos LARGOS (prevemos más de lo que ocurre)"
    else:
        tendencia = "tendemos a quedarnos CORTOS (prevemos menos de lo que ocurre)"
    interp = f"MAPE {m:.1f}% sobre {n} meses; {tendencia}."
    return ResumenError(n, m, s, sr, interp)


def errores_mensuales(real: pd.Series, pred: pd.Series) -> pd.Series:
    """Serie de |error| porcentual por mes (para detectar deriva)."""
    df = pd.concat([real.rename("real"), pred.rename("pred")], axis=1).dropna()
    df = df[df["real"] != 0]
    return (np.abs((df["real"] - df["pred"]) / df["real"]) * 100.0)


def alerta_deriva(real: pd.Series, pred: pd.Series) -> tuple[bool, str]:
    """True si los últimos N meses consecutivos superan el umbral de error.

    N y umbral vienen de config.UMBRALES_ALERTA. Devuelve (hay_alerta, mensaje).
    """
    err = errores_mensuales(real, pred).sort_index()
    n_req = UMBRALES_ALERTA.meses_consecutivos_deriva
    umbral = UMBRALES_ALERTA.mape_umbral_deriva
    if len(err) < n_req:
        return False, "Histórico insuficiente para evaluar deriva."
    ultimos = err.tail(n_req)
    if (ultimos > umbral).all():
        return True, (
            f"⚠️ Deriva: los últimos {n_req} meses superan el {umbral:.0f}% de error "
            f"(MAPE reciente {ultimos.mean():.1f}%). Conviene recalcular/revisar el modelo."
        )
    return False, f"Sin deriva: error reciente por debajo del umbral ({umbral:.0f}%)."
