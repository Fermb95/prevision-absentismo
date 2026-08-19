"""
ui/pagina_segmentacion.py — Página: Segmentación dentro del centro.

Baja el grano del absentismo a subgrupos AGREGADOS (turno × puesto × franja de
carga) para saber DÓNDE actuar dentro de un almacén, sin señalar a personas.
Prioriza por IMPACTO (jornadas perdidas al mes), no solo por tasa.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modelo.segmentacion import (
    anadir_franjas_carga,
    carga_vs_absentismo,
    focos,
    por_dimension,
    tabla_segmentos,
)
from ui import servicios
from ui.graficos import CONFIG_PLOTLY
from ui.sidebar import Seleccion

_AZUL = "#2563eb"


def _heatmap(tabla: pd.DataFrame) -> go.Figure:
    piv = tabla.pivot_table(index="puesto", columns="turno", values="tasa_media")
    orden = [t for t in ("manana", "tarde", "noche") if t in piv.columns]
    piv = piv.reindex(columns=orden)
    fig = go.Figure(go.Heatmap(
        z=piv.to_numpy(),
        x=[servicios.turno_bonito(t) for t in piv.columns], y=piv.index,
        colorscale="RdYlGn", reversescale=True,
        zmin=0, zmax=max(0.15, float(np.nanmax(piv.to_numpy()))),
        colorbar=dict(title="Tasa", tickformat=".0%"),
        text=[[f"{v:.1%}" if pd.notna(v) else "" for v in fila] for fila in piv.to_numpy()],
        texttemplate="%{text}", hovertemplate="%{y} · %{x}: %{z:.1%}<extra></extra>",
    ))
    fig.update_layout(title="Absentismo por puesto y turno", height=380,
                      margin=dict(l=10, r=10, t=50, b=10), template="plotly_white",
                      paper_bgcolor="rgba(0,0,0,0)")
    return fig


def _barras(dim_df: pd.DataFrame, etiqueta: str, titulo: str) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=dim_df[etiqueta].astype(str).str.capitalize(), y=dim_df["tasa_media"],
        marker_color=_AZUL, text=[f"{v:.1%}" for v in dim_df["tasa_media"]],
        textposition="outside",
    ))
    fig.update_layout(title=titulo, height=340, margin=dict(l=10, r=10, t=50, b=10),
                      template="plotly_white", paper_bgcolor="rgba(0,0,0,0)")
    fig.update_yaxes(tickformat=".0%", title="Tasa media", gridcolor="#eef1f5")
    return fig


def _scatter_carga(tabla: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=tabla["carga_media"], y=tabla["tasa_media"], mode="markers",
        marker=dict(size=tabla["plantilla"].clip(6, 40), color=_AZUL, opacity=.7),
        text=[f"{servicios.turno_bonito(t)} · {p}" for t, p in zip(tabla["turno"], tabla["puesto"])],
        hovertemplate="%{text}<br>Carga %{x:.0f} · Tasa %{y:.1%}<extra></extra>",
    ))
    fig.update_layout(title="Carga de trabajo vs. absentismo (cada punto es un subgrupo)",
                      height=360, margin=dict(l=10, r=10, t=50, b=10), template="plotly_white",
                      paper_bgcolor="rgba(0,0,0,0)")
    fig.update_yaxes(tickformat=".0%", title="Tasa media", gridcolor="#eef1f5")
    fig.update_xaxes(title="Carga de trabajo (media)", gridcolor="#eef1f5")
    return fig


def render(sel: Seleccion) -> None:
    st.header("🔬 Segmentación dentro del centro")
    st.caption(
        "Absentismo por **turno × puesto × carga** para localizar el foco dentro del "
        "almacén y actuar sobre las condiciones (turno, carga), sin señalar personas."
    )
    if not servicios.hay_segmentacion(sel.modo):
        st.info(
            "No hay datos de segmentación. Añade las columnas **`puesto`** y **`carga`** "
            "al fichero de absentismo (una fila por centro/turno/puesto/mes) en **Datos**."
        )
        return
    if not sel.centro:
        st.info("Selecciona un centro en la barra lateral.")
        return

    seg = servicios.segmentacion_de(sel.modo, centro=sel.centro)
    tabla = anadir_franjas_carga(tabla_segmentos(seg, centro=sel.centro))
    if tabla.empty:
        st.info("No hay segmentación para este centro.")
        return

    # ---------------- KPIs ----------------
    foco = focos(tabla, top=1)
    jornadas_centro = tabla["jornadas_perdidas_mes"].sum()
    corr = carga_vs_absentismo(tabla)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Subgrupos", servicios.fmt_num(len(tabla)))
    if not foco.empty:
        f = foco.iloc[0]
        c2.metric(
            "Foco de acción",
            f"{servicios.turno_bonito(f['turno'])} · {f['puesto']}",
            help=f"Tasa {servicios.fmt_pct(f['tasa_media'])} · "
                 f"{servicios.fmt_num(f['jornadas_perdidas_mes'],1)} jornadas/mes",
        )
    c3.metric("Jornadas perdidas/mes (centro)", servicios.fmt_num(jornadas_centro, 0))
    c4.metric(
        "Carga ↔ absentismo",
        "—" if pd.isna(corr) else servicios._es(f"{corr:+.2f}"),
        help="Correlación entre carga y absentismo entre subgrupos (−1 a +1).",
    )

    # ---------------- Heatmap ----------------
    st.plotly_chart(_heatmap(tabla), use_container_width=True, config=CONFIG_PLOTLY)

    # ---------------- Focos priorizados por impacto ----------------
    st.subheader("Dónde actuar primero (por jornadas perdidas al mes)")
    prio = focos(tabla, top=10).copy()
    prio["Turno"] = prio["turno"].map(servicios.turno_bonito)
    prio["Puesto"] = prio["puesto"]
    prio["Tasa"] = prio["tasa_media"].map(servicios.fmt_pct)
    prio["Jornadas/mes"] = prio["jornadas_perdidas_mes"].map(lambda x: servicios.fmt_num(x, 1))
    prio["Plantilla"] = prio["plantilla"].map(lambda x: servicios.fmt_num(x, 0))
    prio["Carga"] = prio["carga_media"].map(lambda x: servicios.fmt_num(x, 0))
    prio["Franja"] = prio["franja"].astype("string").str.capitalize()
    st.dataframe(
        prio[["Turno", "Puesto", "Tasa", "Jornadas/mes", "Plantilla", "Carga", "Franja"]],
        hide_index=True, use_container_width=True,
    )
    st.caption(
        "Priorizado por **impacto** (jornadas perdidas al mes): un grupo grande con "
        "tasa moderada pierde más días que uno diminuto con tasa alta."
    )

    # ---------------- Por puesto / por franja ----------------
    col1, col2 = st.columns(2)
    with col1:
        dim_p = por_dimension(tabla, "puesto")
        if not dim_p.empty:
            st.plotly_chart(_barras(dim_p, "puesto", "Absentismo por puesto"),
                            use_container_width=True, config=CONFIG_PLOTLY)
    with col2:
        dim_f = por_dimension(tabla, "franja")
        if not dim_f.empty and dim_f["franja"].notna().any():
            st.plotly_chart(_barras(dim_f, "franja", "Absentismo por franja de carga"),
                            use_container_width=True, config=CONFIG_PLOTLY)

    # ---------------- Carga vs absentismo ----------------
    st.plotly_chart(_scatter_carga(tabla), use_container_width=True, config=CONFIG_PLOTLY)
    if not pd.isna(corr):
        signo = "más" if corr > 0 else "menos"
        st.caption(
            f"En este centro, a mayor carga tiende a haber **{signo} absentismo** "
            f"(correlación {servicios._es(f'{corr:+.2f}')}). Asociación, no causa."
        )
