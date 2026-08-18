"""
modelo/motor.py — Motores de previsión (un objeto por serie centro×turno).

Contrato común `Modelo` con tres implementaciones:
  * ModeloProphet          — motor principal (import perezoso de `prophet`).
  * ModeloSARIMA           — alternativa (import perezoso de `statsmodels`).
  * ModeloEstacionalNaive  — puro numpy/pandas, SIEMPRE disponible. Sirve de
                             degradación elegante si Prophet/SARIMA no están o
                             si hay muy poco histórico.

Todos devuelven, para cada mes previsto: valor central + intervalo (lo, hi) al
nivel de config.PARAMS_MODELO.intervalo_confianza (90%), que se ENSANCHA con el
horizonte. El regresor de gripe lo usa Prophet; los demás lo ignoran (documentado).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from config import PARAMS_MODELO

# z para intervalos habituales (evita depender de scipy en el fallback).
_Z = {0.80: 1.2816, 0.90: 1.6449, 0.95: 1.9600}


def _z_intervalo() -> float:
    return _Z.get(round(PARAMS_MODELO.intervalo_confianza, 2), 1.6449)


# ---------------------------------------------------------------------------
# Utilidades de calendario y series
# ---------------------------------------------------------------------------
def periodo_a_ts(periodo: str) -> pd.Timestamp:
    """'YYYY-MM' → Timestamp del primer día del mes."""
    anio, mes = periodo.split("-")
    return pd.Timestamp(int(anio), int(mes), 1)


def ts_a_periodo(ts: pd.Timestamp) -> str:
    """Timestamp → 'YYYY-MM'."""
    return f"{ts.year:04d}-{ts.month:02d}"


def siguientes_periodos(ultimo_periodo: str, horizonte: int) -> list[str]:
    """Lista de los `horizonte` periodos mensuales posteriores a `ultimo_periodo`."""
    ts = periodo_a_ts(ultimo_periodo)
    return [ts_a_periodo(ts + pd.DateOffset(months=k)) for k in range(1, horizonte + 1)]


def serie_mensual(df_ct: pd.DataFrame) -> pd.Series:
    """Convierte un histórico de un centro×turno en Serie mensual indexada por fecha.

    Espera columnas 'periodo' y 'tasa'. Ordena por periodo y elimina duplicados.
    """
    s = df_ct.dropna(subset=["tasa"]).copy()
    s["ts"] = s["periodo"].map(periodo_a_ts)
    s = s.sort_values("ts").drop_duplicates("ts", keep="last")
    return pd.Series(s["tasa"].to_numpy(dtype=float), index=pd.DatetimeIndex(s["ts"]))


# ---------------------------------------------------------------------------
# Contrato común
# ---------------------------------------------------------------------------
class Modelo(ABC):
    """Interfaz común a todos los motores de previsión."""

    nombre: str = "base"

    def __init__(self) -> None:
        self._ajustado: bool = False

    @abstractmethod
    def ajustar(self, serie: pd.Series, gripe: pd.Series | None = None) -> None:
        """Ajusta el modelo a una serie mensual (índice temporal, valores=tasa)."""

    @abstractmethod
    def prever(
        self, periodos: list[str], gripe_futura: pd.Series | None = None
    ) -> pd.DataFrame:
        """Devuelve DataFrame con columnas: periodo_objetivo, valor, lo, hi."""

    @staticmethod
    def _empaqueta(
        periodos: list[str], valores: np.ndarray, lo: np.ndarray, hi: np.ndarray
    ) -> pd.DataFrame:
        # La tasa no puede ser negativa; el límite inferior tampoco.
        valores = np.clip(valores, 0.0, 0.95)
        lo = np.clip(lo, 0.0, 0.95)
        hi = np.clip(hi, lo, 0.99)
        return pd.DataFrame(
            {"periodo_objetivo": periodos, "valor": valores, "lo": lo, "hi": hi}
        )


# ---------------------------------------------------------------------------
# Motor 1 — Estacional-naive (siempre disponible)
# ---------------------------------------------------------------------------
class ModeloEstacionalNaive(Modelo):
    """Tendencia lineal + estacionalidad mensual aditiva + ruido gaussiano.

    Sencillo, robusto y sin dependencias externas. Captura el pico de invierno
    porque estima un efecto por mes del año. El intervalo se ensancha con el
    horizonte (sigma · sqrt(paso)).
    """

    nombre = "naive"

    def __init__(self) -> None:
        super().__init__()
        self._a = 0.0            # intercepto de tendencia
        self._b = 0.0            # pendiente de tendencia
        self._estacional: dict[int, float] = {}
        self._sigma = 0.01
        self._n = 0

    def ajustar(self, serie: pd.Series, gripe: pd.Series | None = None) -> None:
        y = serie.to_numpy(dtype=float)
        n = len(y)
        self._n = n
        if n == 0:
            raise ValueError("Serie vacía: no se puede ajustar.")

        t = np.arange(n, dtype=float)
        if n >= 3:
            self._b, self._a = np.polyfit(t, y, 1)[0], np.polyfit(t, y, 1)[1]
        else:
            self._a, self._b = float(np.mean(y)), 0.0

        tendencia = self._a + self._b * t
        residuo = y - tendencia

        meses = np.array([ts.month for ts in serie.index])
        estacional: dict[int, float] = {}
        for m in range(1, 13):
            mask = meses == m
            estacional[m] = float(residuo[mask].mean()) if mask.any() else 0.0
        # Centramos el efecto estacional (media 0) para no sesgar el nivel.
        media_est = np.mean([estacional[m] for m in range(1, 13)])
        self._estacional = {m: estacional[m] - media_est for m in range(1, 13)}

        ajustado = tendencia + np.array([self._estacional[m] for m in meses])
        resid_final = y - ajustado
        sigma = float(np.std(resid_final, ddof=1)) if n > 2 else float(np.std(y) or 0.01)
        self._sigma = max(sigma, 1e-4)
        self._ajustado = True

    def prever(
        self, periodos: list[str], gripe_futura: pd.Series | None = None
    ) -> pd.DataFrame:
        if not self._ajustado:
            raise RuntimeError("Modelo no ajustado.")
        z = _z_intervalo()
        valores, lo, hi = [], [], []
        for paso, periodo in enumerate(periodos, start=1):
            t_fut = self._n - 1 + paso
            mes = int(periodo.split("-")[1])
            val = self._a + self._b * t_fut + self._estacional.get(mes, 0.0)
            medio = z * self._sigma * np.sqrt(paso)  # se ensancha con el horizonte
            valores.append(val)
            lo.append(val - medio)
            hi.append(val + medio)
        return self._empaqueta(periodos, np.array(valores), np.array(lo), np.array(hi))


# ---------------------------------------------------------------------------
# Motor 2 — SARIMA (statsmodels)
# ---------------------------------------------------------------------------
class ModeloSARIMA(Modelo):
    """SARIMA de statsmodels. Import perezoso; si falla, el orquestador degrada."""

    nombre = "sarima"

    def __init__(self) -> None:
        super().__init__()
        self._resultado = None
        self._ultimo_ts: pd.Timestamp | None = None

    def ajustar(self, serie: pd.Series, gripe: pd.Series | None = None) -> None:
        from statsmodels.tsa.statespace.sarimax import SARIMAX  # import perezoso

        y = serie.astype(float)
        y.index = pd.DatetimeIndex(y.index).to_period("M").to_timestamp()
        self._ultimo_ts = y.index[-1]

        n = len(y)
        # Con < 24 meses la estacionalidad SARIMA (periodo 12) es inestable:
        # usamos un modelo no estacional en ese caso.
        if n >= 24:
            orden, orden_estacional = (1, 1, 1), (1, 1, 0, 12)
        else:
            orden, orden_estacional = (1, 1, 1), (0, 0, 0, 0)

        modelo = SARIMAX(
            y, order=orden, seasonal_order=orden_estacional,
            enforce_stationarity=False, enforce_invertibility=False,
        )
        self._resultado = modelo.fit(disp=False)
        self._ajustado = True

    def prever(
        self, periodos: list[str], gripe_futura: pd.Series | None = None
    ) -> pd.DataFrame:
        if not self._ajustado or self._resultado is None:
            raise RuntimeError("Modelo no ajustado.")
        alpha = 1.0 - PARAMS_MODELO.intervalo_confianza  # 0.10 → intervalo 90%
        pred = self._resultado.get_forecast(steps=len(periodos))
        media = np.asarray(pred.predicted_mean, dtype=float)
        conf = np.asarray(pred.conf_int(alpha=alpha), dtype=float)
        return self._empaqueta(periodos, media, conf[:, 0], conf[:, 1])


# ---------------------------------------------------------------------------
# Motor 3 — Prophet (motor principal)
# ---------------------------------------------------------------------------
class ModeloProphet(Modelo):
    """Prophet de Meta. Import perezoso; usa la gripe como regresor si se aporta."""

    nombre = "prophet"

    def __init__(self) -> None:
        super().__init__()
        self._m = None
        self._usa_gripe = False

    def ajustar(self, serie: pd.Series, gripe: pd.Series | None = None) -> None:
        from prophet import Prophet  # import perezoso

        df = pd.DataFrame({"ds": pd.DatetimeIndex(serie.index), "y": serie.to_numpy(float)})

        m = Prophet(
            interval_width=PARAMS_MODELO.intervalo_confianza,
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            seasonality_mode="additive",
        )
        # Festivos de España: afinan la estacionalidad (puentes, Navidad, etc.).
        try:
            m.add_country_holidays(country_name="ES")
        except Exception:
            pass  # si la versión de prophet/holidays no lo soporta, seguimos igual
        if gripe is not None and len(gripe) > 0:
            df = df.merge(
                gripe.rename("gripe").rename_axis("ds").reset_index(), on="ds", how="left"
            )
            df["gripe"] = df["gripe"].fillna(gripe.mean())
            m.add_regressor("gripe")
            self._usa_gripe = True
            self._gripe_media = float(gripe.mean())
            self._gripe_hist = gripe

        m.fit(df)
        self._m = m
        self._ajustado = True

    def prever(
        self, periodos: list[str], gripe_futura: pd.Series | None = None
    ) -> pd.DataFrame:
        if not self._ajustado or self._m is None:
            raise RuntimeError("Modelo no ajustado.")
        fechas = [periodo_a_ts(p) for p in periodos]
        futuro = pd.DataFrame({"ds": pd.DatetimeIndex(fechas)})
        if self._usa_gripe:
            # Si no tenemos gripe futura real, rellenamos con la climatología mensual.
            futuro["gripe"] = [self._gripe_para(ts, gripe_futura) for ts in fechas]
        pred = self._m.predict(futuro)
        return self._empaqueta(
            periodos,
            pred["yhat"].to_numpy(float),
            pred["yhat_lower"].to_numpy(float),
            pred["yhat_upper"].to_numpy(float),
        )

    def _gripe_para(self, ts: pd.Timestamp, gripe_futura: pd.Series | None) -> float:
        if gripe_futura is not None and ts in gripe_futura.index:
            return float(gripe_futura.loc[ts])
        # Climatología: media histórica de ese mes del año.
        mismo_mes = [v for t, v in self._gripe_hist.items() if t.month == ts.month]
        return float(np.mean(mismo_mes)) if mismo_mes else self._gripe_media


# ---------------------------------------------------------------------------
# Fábrica + disponibilidad
# ---------------------------------------------------------------------------
_MOTORES: dict[str, type[Modelo]] = {
    "prophet": ModeloProphet,
    "sarima": ModeloSARIMA,
    "naive": ModeloEstacionalNaive,
}


def crear_modelo(nombre: str) -> Modelo:
    """Instancia un motor por nombre ('prophet' | 'sarima' | 'naive')."""
    clase = _MOTORES.get(nombre, ModeloEstacionalNaive)
    return clase()


def motor_disponible(nombre: str) -> bool:
    """Comprueba si el motor pedido puede importarse en este entorno."""
    if nombre == "naive":
        return True
    try:
        if nombre == "prophet":
            import prophet  # noqa: F401
        elif nombre == "sarima":
            import statsmodels  # noqa: F401
        else:
            return False
        return True
    except Exception:
        return False


def motores_disponibles() -> list[str]:
    """Lista de motores que se pueden usar en este entorno (naive siempre)."""
    return [n for n in ("prophet", "sarima", "naive") if motor_disponible(n)]


def mejor_motor_disponible() -> str:
    """Mejor motor disponible por orden de preferencia: prophet > sarima > naive."""
    for nombre in ("prophet", "sarima", "naive"):
        if motor_disponible(nombre):
            return nombre
    return "naive"
