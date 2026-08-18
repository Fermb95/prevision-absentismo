"""
ingesta/bajas_largas.py — Tratamiento de bajas largas (IT prolongada).

Las bajas largas son eventos puntuales de altísimo impacto que distorsionan la
serie y engañan al modelo. Con datos AGREGADOS no podemos ver la baja individual;
solo el total mensual. Por eso el criterio es ROBUSTO y RELATIVO a cada centro:
un mes es "atípico" (baja larga) cuando su tasa supera `factor_baja_larga` veces
la MEDIANA del propio centro×turno. Según la configuración se puede:
  * 'incluir': dejar la serie tal cual.
  * 'topar':   winsorizar (limitar) el mes atípico a ese umbral.
  * 'marcar':  no tocar los valores, pero señalar los meses afectados.

La estacionalidad normal (pico de invierno ~1,3× la mediana) NO se toca; solo los
picos genuinamente extremos. Esta decisión está documentada en el README.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config import DEFINICION_ABSENTISMO, DefinicionAbsentismo


@dataclass
class InformeBajasLargas:
    tratamiento: str
    n_afectadas: int
    filas_afectadas: pd.DataFrame  # subconjunto marcado


def tratar_bajas_largas(
    df: pd.DataFrame,
    definicion: DefinicionAbsentismo = DEFINICION_ABSENTISMO,
) -> tuple[pd.DataFrame, InformeBajasLargas]:
    """Aplica el tratamiento de bajas largas configurado, por centro×turno.

    Espera un DataFrame con al menos 'tasa'. Si están 'centro' y 'turno', el
    umbral se calcula por grupo (recomendado); si no, sobre toda la serie.
    Añade siempre la columna booleana 'baja_larga'. Para 'topar' guarda el
    original en 'tasa_orig'.
    """
    out = df.copy().reset_index(drop=True)
    out["baja_larga"] = False
    trat = definicion.tratamiento_bajas_largas

    if trat == "incluir" or "tasa" not in out.columns:
        return out, InformeBajasLargas(trat, 0, out.iloc[0:0].copy())

    if trat == "topar":
        out["tasa_orig"] = out["tasa"]

    tiene_grupos = "centro" in out.columns and "turno" in out.columns
    grupos = out.groupby(["centro", "turno"]).groups if tiene_grupos else {"__todo__": out.index}

    factor = definicion.factor_baja_larga
    for _, idx in grupos.items():
        idx = list(idx)
        sub = out.loc[idx, "tasa"].astype(float)
        mediana = sub.median()
        if pd.isna(mediana) or mediana <= 0:
            continue
        umbral = mediana * factor
        atipicos = sub > umbral
        for i, es_atipico in zip(idx, atipicos):
            if not es_atipico:
                continue
            out.at[i, "baja_larga"] = True
            if trat == "topar":
                out.at[i, "tasa"] = umbral

    afectadas = out["baja_larga"]
    return out, InformeBajasLargas(
        tratamiento=trat,
        n_afectadas=int(afectadas.sum()),
        filas_afectadas=out.loc[afectadas].copy(),
    )
