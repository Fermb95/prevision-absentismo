"""
ui/pagina_factores.py — Página: Factores (qué características del CENTRO influyen).

Análisis transversal (entre centros/turnos), NO predicción temporal:
  * Flexibilidad vs. rotación: absentismo medio por tipo de horario.
  * Ranking de factores: qué factor del centro se asocia más con el absentismo.
  * Tabla por centro/turno con su absentismo medio y sus factores.

Solo factores AGREGADOS del centro/turno. Nunca datos de personas ni
características protegidas (sexo, edad, discapacidad, afiliación sindical).
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modelo.factores import (
    comparar_flexibilidad_rotacion,
    ranking_factores,
    tabla_factores_absentismo,
)
from ui import servicios
from ui.graficos import CONFIG_PLOTLY
from ui.sidebar import Seleccion

_COLOR_ROJO = "#dc2626"
_COLOR_VERDE = "#16a34a"
_COLOR_AZUL = "#2563eb"


def _grafico_flex_rotacion(comp: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=[t.capitalize() for t in comp["tipo_horario"]],
        y=comp["tasa_media"],
        marker_color=_COLOR_AZUL,
        text=[f"{v:.1%}" for v in comp["tasa_media"]],
        textposition="outside",
    ))
    fig.update_layout(
        title="Absentismo medio según el tipo de horario",
        height=380, margin=dict(l=10, r=10, t=50, b=10), template="plotly_white",
        font=dict(family="Inter, Segoe UI, sans-serif", color="#111827"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_yaxes(tickformat=".0%", title="Tasa media", gridcolor="#eef1f5")
    return fig


def _grafico_ranking(rank: pd.DataFrame) -> go.Figure:
    r = rank.dropna(subset=["correlacion"]).iloc[::-1]  # menor arriba → mayor abajo
    colores = [_COLOR_ROJO if c > 0 else _COLOR_VERDE for c in r["correlacion"]]
    fig = go.Figure(go.Bar(
        x=r["correlacion"], y=r["nombre"], orientation="h",
        marker_color=colores,
        text=[f"{c:+.2f}" for c in r["correlacion"]], textposition="outside",
    ))
    fig.update_layout(
        title="Asociación de cada factor con el absentismo (correlación)",
        height=360, margin=dict(l=10, r=10, t=50, b=10), template="plotly_white",
        font=dict(family="Inter, Segoe UI, sans-serif", color="#111827"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(title="− menos absentismo   ·   + más absentismo",
                     range=[-1, 1], gridcolor="#eef1f5", zeroline=True,
                     zerolinecolor="#9aa4b2")
    return fig


def render(sel: Seleccion) -> None:
    st.header("🧭 Factores del centro")
    st.caption(
        "Qué características **del centro/turno** (no de las personas) se asocian con "
        "más o menos absentismo. Es un análisis entre centros, para actuar sobre el "
        "diseño del puesto: horario, rotación, satisfacción…"
    )

    if not servicios.hay_factores(sel.modo):
        st.info(
            "No hay factores cargados en este modo. Añádelos como columnas del fichero "
            "de absentismo (`tipo_horario`, `rotacion_pct`, `antiguedad_media`, "
            "`satisfaccion_media`, `jornada_media`) en la página **Datos**."
        )
        return

    hist = servicios.historico_de(sel.modo)
    fac = servicios.factores_de(sel.modo)
    tabla = tabla_factores_absentismo(hist, fac)
    if tabla.empty:
        st.info("No hay suficientes datos para cruzar factores con absentismo.")
        return

    # Excluimos el agregado 'todos' del análisis para no duplicar.
    tabla_ct = tabla[tabla["turno"] != "todos"]

    # --- 1. Flexibilidad vs. rotación ---
    st.subheader("Flexibilidad vs. rotación")
    comp = comparar_flexibilidad_rotacion(tabla_ct)
    if not comp.empty:
        c1, c2 = st.columns([3, 2])
        c1.plotly_chart(_grafico_flex_rotacion(comp), use_container_width=True,
                        config=CONFIG_PLOTLY)
        tabla_comp = comp.copy()
        tabla_comp["Tipo de horario"] = tabla_comp["tipo_horario"].str.capitalize()
        tabla_comp["Absentismo medio"] = tabla_comp["tasa_media"].map(servicios.fmt_pct)
        tabla_comp["Nº centros/turnos"] = tabla_comp["n"]
        c2.dataframe(
            tabla_comp[["Tipo de horario", "Absentismo medio", "Nº centros/turnos"]],
            hide_index=True, use_container_width=True,
        )
        if len(comp) >= 2:
            peor, mejor = comp.iloc[0], comp.iloc[-1]
            dif = (peor["tasa_media"] - mejor["tasa_media"]) * 100
            st.markdown(
                f"➡️ Los turnos **{peor['tipo_horario']}** promedian "
                f"**{servicios.fmt_pct(peor['tasa_media'])}** frente a "
                f"**{servicios.fmt_pct(mejor['tasa_media'])}** de los "
                f"**{mejor['tipo_horario']}** — una diferencia de "
                f"**{servicios._es(f'{dif:.1f}')} puntos**."
            )

    st.divider()

    # --- 2. Ranking de factores ---
    st.subheader("¿Qué factores influyen más?")
    rank = ranking_factores(tabla_ct)
    if rank.empty or rank["correlacion"].isna().all():
        st.info("Aún no hay variación suficiente en los factores para medir asociaciones.")
    else:
        st.plotly_chart(_grafico_ranking(rank), use_container_width=True, config=CONFIG_PLOTLY)
        st.caption(
            "Correlación entre −1 y +1. **Positiva** (rojo): a más factor, más "
            "absentismo. **Negativa** (verde): a más factor, menos. Es una "
            "**asociación, no una causa**, y con pocos centros conviene tomarla como "
            "orientación, no como verdad absoluta."
        )

    st.divider()

    # --- 3. Tabla por centro/turno ---
    st.subheader("Detalle por centro y turno")
    det = tabla_ct.copy()
    det["turno"] = det["turno"].map(servicios.turno_bonito)
    det["Absentismo medio"] = det["tasa_media"].map(servicios.fmt_pct)
    if "tipo_horario" in det.columns:
        det["tipo_horario"] = det["tipo_horario"].str.capitalize()
    columnas = {
        "centro": "Centro", "turno": "Turno", "Absentismo medio": "Absentismo medio",
        "tipo_horario": "Horario", "rotacion_pct": "Rotación (%)",
        "antiguedad_media": "Antigüedad", "satisfaccion_media": "Satisfacción",
        "jornada_media": "Jornada (h)",
    }
    presentes = [c for c in columnas if c in det.columns]
    st.dataframe(
        det[presentes].rename(columns=columnas).sort_values("Absentismo medio", ascending=False),
        hide_index=True, use_container_width=True,
    )
