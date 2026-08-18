"""
ui/pagina_precision.py — Página 2: Precisión (previsión vs. realidad).

Dos herramientas:
  1. Previsión GUARDADA a una fecha pasada contra lo que ocurrió de verdad, con
     MAPE, sesgo (cortos/largos) y alerta de deriva.
  2. BACKTEST: "ponte a fecha X usando solo lo que se sabía entonces y predice",
     para evaluar el modelo aunque no hubiera previsiones guardadas de esa fecha.
"""
from __future__ import annotations

from datetime import datetime, time

import pandas as pd
import streamlit as st

from modelo.backtest import backtest_punto
from modelo.metricas import alerta_deriva, resumen_error
from modelo.motor import motores_disponibles
from persistencia import previsiones
from ui import servicios
from ui.graficos import grafico_precision
from ui.sidebar import Seleccion


def _serie_real(hist_ct: pd.DataFrame) -> pd.Series:
    return pd.Series(hist_ct["tasa"].to_numpy(float), index=hist_ct["periodo"].tolist())


def _bloque_metricas(df: pd.DataFrame) -> None:
    """Pinta MAPE, sesgo y alerta de deriva a partir de un df con 'periodo_objetivo',
    'valor' y 'real'."""
    comparable = df.dropna(subset=["real"])
    if comparable.empty:
        st.info("Todavía no hay meses reales que comparar con esta previsión.")
        return
    real = pd.Series(comparable["real"].to_numpy(float), index=comparable["periodo_objetivo"])
    pred = pd.Series(comparable["valor"].to_numpy(float), index=comparable["periodo_objetivo"])

    r = resumen_error(real, pred)
    c1, c2, c3 = st.columns(3)
    c1.metric("MAPE", f"{servicios._es(f'{r.mape:.1f}')} %",
              help="Error porcentual absoluto medio sobre los meses comparados.")
    c2.metric("Sesgo", f"{servicios._es(f'{r.sesgo_relativo:+.1f}')} %",
              help="Positivo = nos pasamos (largos). Negativo = nos quedamos cortos.")
    c3.metric("Meses comparados", str(r.n))
    st.caption(r.interpretacion)

    hay, msg = alerta_deriva(real, pred)
    (st.error if hay else st.success)(msg)


def render(sel: Seleccion) -> None:
    st.header("🎯 Precisión (previsión vs. realidad)")
    if not sel.centro or not sel.turno:
        st.info("Selecciona un centro y un turno en la barra lateral.")
        return

    hist = servicios.historico_de(sel.modo, sel.centro, sel.turno).sort_values("periodo")
    if hist.empty:
        st.info("No hay histórico para esta combinación.")
        return

    tab1, tab2 = st.tabs(["Previsión guardada vs. realidad", "Backtest (evaluar a fecha X)"])

    # ---------------- 1. Previsión guardada vs realidad ----------------
    with tab1:
        st.caption(
            f"Se lee la previsión que estaba guardada a fecha "
            f"**{servicios.fmt_fecha(sel.fecha_analisis)}** (ajústala en la barra lateral) "
            "y se compara con lo que ocurrió de verdad."
        )
        tope = datetime.combine(sel.fecha_analisis, time.max)
        prev = previsiones.leer_prevision_a_fecha(tope, sel.centro, sel.turno, modo=sel.modo)
        if prev.empty:
            st.warning(
                "No hay previsión guardada a esa fecha para este centro/turno. "
                "Usa la pestaña **Backtest** para evaluar el modelo igualmente."
            )
        else:
            real = _serie_real(hist)
            prev = prev.sort_values("periodo_objetivo")
            prev["real"] = prev["periodo_objetivo"].map(real.to_dict())
            _bloque_metricas(prev)
            st.plotly_chart(
                grafico_precision(prev, titulo=f"{sel.centro} · {sel.turno}"),
                use_container_width=True,
            )

    # ---------------- 2. Backtest ----------------
    with tab2:
        st.caption(
            "Ponte a un mes de corte: el modelo se entrena SOLO con lo anterior a "
            "esa fecha y predice los meses siguientes, que comparamos con lo real."
        )
        periodos = hist["periodo"].tolist()
        if len(periodos) < 7:
            st.info("Hace falta algo más de histórico para un backtest con sentido.")
            return

        col_a, col_b = st.columns(2)
        # Por defecto, un corte que deje unos meses por delante para comparar.
        idx_def = max(0, len(periodos) - 7)
        corte = col_a.selectbox(
            "Mes de corte", options=periodos, index=idx_def,
            format_func=servicios.periodo_bonito,
        )
        motores = motores_disponibles()
        motor = col_b.selectbox("Motor", options=motores, index=0)

        bt = backtest_punto(hist, corte, horizonte=sel.horizonte, motor=motor)
        _bloque_metricas(bt)
        st.plotly_chart(
            grafico_precision(
                bt, titulo=f"Backtest desde {servicios.periodo_bonito(corte)} · {motor}"
            ),
            use_container_width=True,
        )
