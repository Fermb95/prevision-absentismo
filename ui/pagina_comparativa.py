"""
ui/pagina_comparativa.py — Página: Comparativa de previsiones.

Superpone dos tandas de previsión (por defecto, la más reciente frente a la
anterior) para un centro×turno, y muestra cómo ha cambiado la previsión mes a
mes. Útil para responder "¿qué preveíamos el mes pasado y qué prevemos ahora?".
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from persistencia import previsiones
from ui import servicios
from ui.graficos import CONFIG_PLOTLY, grafico_comparativa
from ui.sidebar import Seleccion


def _etiqueta_tanda(fila: pd.Series) -> str:
    fecha = str(fila["fecha_calculo"])[:16]
    return f"{fecha} · {fila['modelo']}"


def render(sel: Seleccion) -> None:
    st.header("🔀 Comparativa de previsiones")
    st.caption(
        "Compara dos recálculos distintos para ver cómo ha cambiado la previsión "
        "(por ejemplo, la de este mes frente a la del mes pasado)."
    )
    if not sel.centro or not sel.turno:
        st.info("Selecciona un centro y un turno en la barra lateral.")
        return

    ejec = previsiones.listar_ejecuciones(modo=sel.modo)
    if len(ejec) < 2:
        st.warning(
            "Aún no hay dos tandas de previsión para comparar. Ve a **Datos** y pulsa "
            "**Recalcular previsión** al menos dos veces (en momentos distintos)."
        )
        return

    ejec = ejec.reset_index(drop=True)
    etiquetas = {row["id_ejecucion"]: _etiqueta_tanda(row) for _, row in ejec.iterrows()}
    ids = ejec["id_ejecucion"].tolist()

    col1, col2 = st.columns(2)
    id_nueva = col1.selectbox(
        "Previsión más reciente", options=ids, index=0,
        format_func=lambda i: etiquetas[i],
    )
    # La anterior por defecto es la segunda más reciente.
    id_antigua = col2.selectbox(
        "Previsión anterior", options=ids, index=1,
        format_func=lambda i: etiquetas[i],
    )
    if id_nueva == id_antigua:
        st.info("Elige dos tandas distintas para comparar.")
        return

    nueva = previsiones.leer_tanda(id_nueva, modo=sel.modo)
    antigua = previsiones.leer_tanda(id_antigua, modo=sel.modo)
    filtro = lambda d: d[(d["centro"] == sel.centro) & (d["turno"] == sel.turno)] \
        .sort_values("periodo_objetivo")
    nueva, antigua = filtro(nueva), filtro(antigua)

    hist = servicios.historico_de(sel.modo, sel.centro, sel.turno)

    # --- Gráfico ---
    fig = grafico_comparativa(
        hist, nueva, antigua,
        etiqueta_nueva=str(ejec[ejec["id_ejecucion"] == id_nueva]["fecha_calculo"].iloc[0])[:10],
        etiqueta_antigua=str(ejec[ejec["id_ejecucion"] == id_antigua]["fecha_calculo"].iloc[0])[:10],
        titulo=f"{sel.centro} · {servicios.turno_bonito(sel.turno)}",
    )
    st.plotly_chart(fig, use_container_width=True, config=CONFIG_PLOTLY)

    # --- Tabla de diferencias mes a mes ---
    comp = nueva.merge(
        antigua[["periodo_objetivo", "valor"]], on="periodo_objetivo",
        how="inner", suffixes=("_nueva", "_antigua"),
    )
    if comp.empty:
        st.info("Las dos tandas no comparten meses previstos para comparar.")
        return

    comp["dif_pp"] = (comp["valor_nueva"] - comp["valor_antigua"]) * 100
    filas = []
    for _, r in comp.iterrows():
        dif = float(r["dif_pp"])
        flecha = "🔺" if dif > 0.05 else ("🔻" if dif < -0.05 else "➖")
        dif_txt = servicios._es(f"{dif:+.1f}")
        filas.append({
            "Mes": servicios.periodo_bonito(r["periodo_objetivo"]),
            "Previsión anterior": servicios.fmt_pct(r["valor_antigua"]),
            "Previsión nueva": servicios.fmt_pct(r["valor_nueva"]),
            "Diferencia": f"{flecha} {dif_txt} pp",
        })
    tabla = pd.DataFrame(filas)

    # KPI de cambio medio.
    cambio_medio = comp["dif_pp"].mean()
    signo = "sube" if cambio_medio > 0 else ("baja" if cambio_medio < 0 else "no cambia")
    st.metric(
        "Cambio medio de la previsión",
        f"{servicios._es(f'{cambio_medio:+.2f}')} pp",
        help=f"En promedio, la nueva previsión {signo} respecto a la anterior.",
    )
    st.dataframe(tabla, hide_index=True, use_container_width=True)
    st.caption("pp = puntos porcentuales. 🔺 sube · 🔻 baja · ➖ sin cambio apreciable.")
