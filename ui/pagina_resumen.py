"""
ui/pagina_resumen.py — Página: Resumen (visión global de todos los centros).

Muestra de un vistazo la tasa prevista del PRÓXIMO mes para todas las
combinaciones centro×turno: un heatmap semáforo y una tabla ordenada de peor a
mejor, con las personas equivalentes a cubrir. Pensada para que Prevención/RRHH
prioricen sin revisar centro por centro.

Lee la previsión ya guardada (no recalcula).
"""
from __future__ import annotations

from datetime import datetime, time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from persistencia import previsiones
from ui import servicios
from ui.graficos import CONFIG_PLOTLY
from ui.sidebar import Seleccion

_ORDEN_TURNOS = ["manana", "tarde", "noche"]


def _heatmap(pivot: pd.DataFrame) -> go.Figure:
    fig = go.Figure(
        go.Heatmap(
            z=pivot.to_numpy(),
            x=[servicios.turno_bonito(t) for t in pivot.columns],
            y=pivot.index,
            colorscale="RdYlGn",
            reversescale=True,             # verde=bajo, rojo=alto
            zmin=0, zmax=max(0.15, float(pivot.to_numpy().max() or 0.15)),
            colorbar=dict(title="Tasa", tickformat=".0%"),
            text=[[f"{v:.1%}" if pd.notna(v) else "" for v in fila] for fila in pivot.to_numpy()],
            texttemplate="%{text}",
            hovertemplate="%{y} · %{x}: %{z:.1%}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Tasa prevista del próximo mes por centro y turno",
        height=430, margin=dict(l=10, r=10, t=50, b=10), template="plotly_white",
    )
    return fig


def render(sel: Seleccion) -> None:
    st.header("🗺️ Resumen de todos los centros")
    st.caption(
        "Previsión del **próximo mes** para cada centro y turno, leída de la última "
        "previsión guardada. Verde = bajo, rojo = alto (umbrales configurables)."
    )

    tope = datetime.combine(sel.fecha_analisis, time.max)
    prev = previsiones.leer_prevision_a_fecha(tope, modo=sel.modo)
    if prev.empty:
        st.warning(
            "No hay ninguna previsión guardada a esta fecha. Ve a **Datos** y pulsa "
            "**Recalcular previsión**."
        )
        return

    # Próximo mes = el primer periodo objetivo de la tanda.
    proximo = prev["periodo_objetivo"].min()
    prox = prev[prev["periodo_objetivo"] == proximo].copy()
    st.subheader(f"Próximo mes: {servicios.periodo_bonito(proximo)}")

    # --- Alerta de centros en rojo (por encima del umbral ámbar) ---
    rojos = prox[prox["valor"] > config.UMBRALES_SEMAFORO.ambar_max]
    rojos = rojos[rojos["turno"] != "todos"].sort_values("valor", ascending=False)
    if not rojos.empty:
        items = " · ".join(
            f"{r['centro']}/{servicios.turno_bonito(r['turno'])} "
            f"({servicios.fmt_pct(r['valor'])})"
            for _, r in rojos.iterrows()
        )
        st.markdown(
            f'<div class="alerta-roja">🔴 <b>{len(rojos)} '
            f'{"combinación" if len(rojos) == 1 else "combinaciones"} en rojo</b> '
            f'(por encima del {servicios.fmt_pct(config.UMBRALES_SEMAFORO.ambar_max)}): '
            f"{items}</div>",
            unsafe_allow_html=True,
        )

    # Plantilla de referencia por centro×turno (para las personas a cubrir).
    hist = servicios.historico_de(sel.modo)
    plantillas = (
        hist.dropna(subset=["plantilla"]).sort_values("periodo")
        .groupby(["centro", "turno"])["plantilla"].last()
    )

    filas = []
    for _, r in prox.iterrows():
        pl = plantillas.get((r["centro"], r["turno"]), float("nan"))
        emoji, _nivel = servicios.clasificar_semaforo(r["valor"])
        filas.append({
            "": emoji,
            "Centro": r["centro"],
            "Turno": servicios.turno_bonito(r["turno"]),
            "Tasa prevista": r["valor"],
            "Intervalo 90%": f"{servicios.fmt_pct(r['lo'])} – {servicios.fmt_pct(r['hi'])}",
            "Personas a cubrir": servicios.fte_ausentes(r["valor"], pl),
            "Refuerzo (peor caso)": servicios.refuerzo_recomendado(r["hi"], pl),
        })
    tabla = pd.DataFrame(filas).sort_values("Tasa prevista", ascending=False)

    # --- Heatmap (solo turnos individuales, sin el agregado 'todos') ---
    solo_turnos = prox[prox["turno"].isin(_ORDEN_TURNOS)]
    if not solo_turnos.empty:
        pivot = (
            solo_turnos.pivot_table(index="centro", columns="turno", values="valor")
            .reindex(columns=[t for t in _ORDEN_TURNOS if t in solo_turnos["turno"].unique()])
        )
        st.plotly_chart(_heatmap(pivot), use_container_width=True, config=CONFIG_PLOTLY)

    # --- Tabla ordenada de peor a mejor ---
    st.markdown("**Detalle (de peor a mejor)**")
    tabla_fmt = tabla.copy()
    tabla_fmt["Tasa prevista"] = tabla_fmt["Tasa prevista"].map(servicios.fmt_pct)
    tabla_fmt["Personas a cubrir"] = tabla_fmt["Personas a cubrir"].map(
        lambda x: servicios.fmt_num(x, 1)
    )
    st.dataframe(tabla_fmt, hide_index=True, use_container_width=True)

    u = config.UMBRALES_SEMAFORO
    st.caption(
        f"Semáforo: 🟢 < {servicios.fmt_pct(u.verde_max)} · "
        f"🟡 {servicios.fmt_pct(u.verde_max)}–{servicios.fmt_pct(u.ambar_max)} · "
        f"🔴 > {servicios.fmt_pct(u.ambar_max)}. "
        "«Personas a cubrir» = tasa × plantilla; «Refuerzo» cubre el peor caso del intervalo 90%."
    )

    # --- Exportar ---
    st.divider()
    _bloque_exportar(sel, prev, hist)


def _bloque_exportar(sel: Seleccion, prev: pd.DataFrame, hist: pd.DataFrame) -> None:
    st.markdown("**Exportar**")
    c1, c2 = st.columns(2)
    excel = servicios.construir_excel({"prevision": prev, "historico": hist})
    c1.download_button(
        "⬇️ Descargar TODO en Excel", data=excel,
        file_name=f"absentismo_{sel.modo}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    c2.download_button(
        "⬇️ Previsión en CSV", data=servicios.a_csv_bytes(prev),
        file_name=f"prevision_{sel.modo}.csv", mime="text/csv",
    )
