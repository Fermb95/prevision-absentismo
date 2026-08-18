"""
ui/pagina_prevision.py — Página 1: Previsión.

KPIs (tasa prevista del próximo mes con intervalo, jornadas perdidas previstas
con rango, media del horizonte, variación interanual) + gráfico histórico +
previsión con banda 90%, marca HOY y zonas de gripe.

Lee la previsión YA GUARDADA vigente a la fecha de análisis (no recalcula).
"""
from __future__ import annotations

from datetime import datetime, time

import streamlit as st

from persistencia import previsiones
from ui import servicios
from ui.graficos import CONFIG_PLOTLY, grafico_prevision
from ui.sidebar import Seleccion


def render(sel: Seleccion) -> None:
    st.header("📈 Previsión")
    if not sel.centro or not sel.turno:
        st.info("Selecciona un centro y un turno en la barra lateral.")
        return

    hist = servicios.historico_de(sel.modo, sel.centro, sel.turno).sort_values("periodo")
    if hist.empty:
        st.info("No hay histórico para esta combinación.")
        return

    # Previsión guardada vigente a la fecha de análisis (no recalcula al vuelo).
    tope = datetime.combine(sel.fecha_analisis, time.max)
    prev = previsiones.leer_prevision_a_fecha(tope, sel.centro, sel.turno, modo=sel.modo)
    if prev.empty:
        st.warning(
            "No hay ninguna previsión guardada a esta fecha. Ve a la página **Datos** "
            "y pulsa **Recalcular previsión** para generar una."
        )
        st.plotly_chart(
            grafico_prevision(hist, prev, titulo=f"{sel.centro} · {servicios.turno_bonito(sel.turno)}"),
            use_container_width=True, config=CONFIG_PLOTLY,
        )
        return

    prev = prev.sort_values("periodo_objetivo").head(sel.horizonte).reset_index(drop=True)

    # Badge de fiabilidad de esta serie.
    fiab = servicios.fiabilidad_de(hist)
    if fiab == "alta":
        st.caption("🟩 Fiabilidad **alta** (histórico suficiente).")
    else:
        st.caption("🟨 Fiabilidad **baja**: poco histórico, tómalo con cautela.")

    # ---------------- KPIs ----------------
    por_mes, media_teor = servicios.jornadas_teoricas_ref(hist)
    prox = prev.iloc[0]
    mes_prox = int(prox["periodo_objetivo"][5:7])
    teor_prox = por_mes.get(mes_prox, media_teor)

    jorn_central = prox["valor"] * teor_prox
    jorn_lo = prox["lo"] * teor_prox
    jorn_hi = prox["hi"] * teor_prox
    media_horizonte = prev["valor"].mean()
    emoji, _nivel = servicios.clasificar_semaforo(prox["valor"])

    # Variación interanual: próximo mes previsto vs mismo mes del año anterior (real).
    anio_prev = int(prox["periodo_objetivo"][:4]) - 1
    periodo_hace_un_anio = f"{anio_prev}-{prox['periodo_objetivo'][5:7]}"
    fila_ant = hist[hist["periodo"] == periodo_hace_un_anio]
    if not fila_ant.empty:
        tasa_ant = float(fila_ant["tasa"].iloc[0])
        delta_i000 = (prox["valor"] - tasa_ant) * 100  # en puntos porcentuales
        variacion_txt = f"{delta_i000:+.1f} pp vs {servicios.periodo_bonito(periodo_hace_un_anio)}"
    else:
        variacion_txt = "sin dato del año anterior"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        f"Tasa prevista · {servicios.periodo_bonito(prox['periodo_objetivo'])}",
        f"{emoji} {servicios.fmt_pct(prox['valor'])}",
        help=f"Intervalo 90%: {servicios.fmt_pct(prox['lo'])} – {servicios.fmt_pct(prox['hi'])}",
    )
    c2.metric(
        "Jornadas perdidas previstas",
        servicios.fmt_num(jorn_central, 0),
        help=f"Rango 90%: {servicios.fmt_num(jorn_lo,0)} – {servicios.fmt_num(jorn_hi,0)} jornadas",
    )
    c3.metric(f"Media prevista ({sel.horizonte} meses)", servicios.fmt_pct(media_horizonte))
    c4.metric("Variación interanual", variacion_txt)

    # ---------------- Dimensionamiento de plantilla ----------------
    plantilla = servicios.plantilla_ref(hist)
    fte = servicios.fte_ausentes(prox["valor"], plantilla)
    fte_lo = servicios.fte_ausentes(prox["lo"], plantilla)
    fte_hi = servicios.fte_ausentes(prox["hi"], plantilla)
    refuerzo = servicios.refuerzo_recomendado(prox["hi"], plantilla)

    d1, d2 = st.columns(2)
    d1.metric(
        "Personas equivalentes ausentes (próx. mes)",
        servicios.fmt_num(fte, 1),
        help=f"= tasa × plantilla ({servicios.fmt_num(plantilla,0)} pers.). "
             f"Rango 90%: {servicios.fmt_num(fte_lo,1)} – {servicios.fmt_num(fte_hi,1)}",
    )
    d2.metric(
        "Refuerzo recomendado (peor caso 90%)",
        f"{servicios.fmt_num(refuerzo,0)} pers.",
        help="Personas a tener disponibles para cubrir el límite superior del intervalo.",
    )

    st.caption(
        f"Intervalo 90% del próximo mes: **{servicios.fmt_pct(prox['lo'])} – "
        f"{servicios.fmt_pct(prox['hi'])}**. Modelo: **{prox['modelo']}**."
    )

    # ---------------- Gráfico ----------------
    st.plotly_chart(
        grafico_prevision(hist, prev, titulo=f"{sel.centro} · {servicios.turno_bonito(sel.turno)}"),
        use_container_width=True, config=CONFIG_PLOTLY,
    )

    with st.expander("Ver tabla de previsión"):
        tabla = prev.copy()
        tabla["periodo"] = tabla["periodo_objetivo"].map(servicios.periodo_bonito)
        tabla["tasa prevista"] = tabla["valor"].map(servicios.fmt_pct)
        tabla["intervalo 90%"] = [
            f"{servicios.fmt_pct(lo)} – {servicios.fmt_pct(hi)}"
            for lo, hi in zip(tabla["lo"], tabla["hi"])
        ]
        st.dataframe(
            tabla[["periodo", "tasa prevista", "intervalo 90%"]],
            hide_index=True, use_container_width=True,
        )

    # ---------------- Exportar (este centro×turno) ----------------
    # `prev` ya trae centro/turno (viene de la tabla previsiones); seleccionamos
    # solo las columnas útiles para el informe.
    cols_exp = [c for c in ("centro", "turno", "periodo_objetivo", "valor", "lo", "hi", "modelo")
                if c in prev.columns]
    exp = prev[cols_exp].copy()
    c1, c2 = st.columns(2)
    c1.download_button(
        "⬇️ Previsión en Excel", data=servicios.construir_excel({"prevision": exp, "historico": hist}),
        file_name=f"prevision_{sel.centro}_{sel.turno}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    c2.download_button(
        "⬇️ Previsión en CSV", data=servicios.a_csv_bytes(exp),
        file_name=f"prevision_{sel.centro}_{sel.turno}.csv", mime="text/csv",
    )
