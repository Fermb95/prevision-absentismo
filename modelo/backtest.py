"""
modelo/backtest.py — Validación TEMPORAL (nunca partición aleatoria).

Permite evaluar el modelo "a toro pasado": ponte a una fecha de corte usando
SOLO el histórico anterior a esa fecha, predice los meses siguientes y compara
con lo que ocurrió de verdad. Sirve para la página de Precisión aunque no
tuviéramos previsiones guardadas de aquella fecha.
"""
from __future__ import annotations

import pandas as pd

from config import PARAMS_MODELO
from modelo.motor import crear_modelo, motor_disponible, serie_mensual, siguientes_periodos


def backtest_punto(
    historico_ct: pd.DataFrame,
    periodo_corte: str,
    horizonte: int = max(PARAMS_MODELO.horizontes_meses),
    motor: str = PARAMS_MODELO.motor_por_defecto,
    gripe: pd.Series | None = None,
) -> pd.DataFrame:
    """Entrena con periodos <= corte y predice los `horizonte` meses siguientes.

    historico_ct: histórico de UN centro×turno (columnas 'periodo','tasa').
    Devuelve columnas: periodo_objetivo, valor, lo, hi, real (lo observado, si existe).
    """
    entrenamiento = historico_ct[historico_ct["periodo"] <= periodo_corte]
    serie = serie_mensual(entrenamiento)
    if len(serie) < PARAMS_MODELO.min_meses_para_ajustar:
        motor_ef = "naive"
    elif motor != "naive" and not motor_disponible(motor):
        motor_ef = "naive"
    else:
        motor_ef = motor

    periodos = siguientes_periodos(serie.index[-1].strftime("%Y-%m"), horizonte)
    modelo = crear_modelo(motor_ef)
    modelo.ajustar(serie, gripe=gripe)
    prev = modelo.prever(periodos, gripe_futura=gripe)

    # Adjuntamos lo REAL (de todo el histórico, incluidos meses posteriores al corte).
    real = (
        historico_ct[["periodo", "tasa"]]
        .rename(columns={"periodo": "periodo_objetivo", "tasa": "real"})
    )
    prev = prev.merge(real, on="periodo_objetivo", how="left")
    prev["modelo"] = motor_ef
    return prev


def backtest_expansivo(
    historico_ct: pd.DataFrame,
    horizonte: int = 1,
    motor: str = PARAMS_MODELO.motor_por_defecto,
    min_entrenamiento: int | None = None,
) -> pd.DataFrame:
    """Backtest de ventana expansiva: para cada corte válido, predice `horizonte`
    meses y guarda predicción vs real. Devuelve la concatenación de todos los cortes.

    Útil para estimar el error del modelo de forma honesta (validación temporal).
    """
    minimo = min_entrenamiento or PARAMS_MODELO.min_meses_para_ajustar
    serie = serie_mensual(historico_ct)
    periodos_hist = [ts.strftime("%Y-%m") for ts in serie.index]

    resultados: list[pd.DataFrame] = []
    # Cortamos en cada punto que deje al menos `minimo` meses de entrenamiento y
    # que tenga al menos 1 mes real por delante para comparar.
    for i in range(minimo, len(periodos_hist) - horizonte + 1):
        corte = periodos_hist[i - 1]
        prev = backtest_punto(historico_ct, corte, horizonte=horizonte, motor=motor)
        prev = prev.dropna(subset=["real"]).head(horizonte)
        prev["periodo_corte"] = corte
        resultados.append(prev)

    if not resultados:
        return pd.DataFrame(
            columns=["periodo_objetivo", "valor", "lo", "hi", "real", "modelo", "periodo_corte"]
        )
    return pd.concat(resultados, ignore_index=True)
