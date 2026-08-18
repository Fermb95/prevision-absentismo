"""
ui/pagina_datos.py — Página 3: Datos.

  * Descarga de plantillas vacías (formato exacto).
  * Subida de CSV/Excel con vista previa + validación (incluida la barrera que
    rechaza columnas personales).
  * Botón "Recalcular previsión" (crea una nueva tanda; NO ocurre al abrir la app).
"""
from __future__ import annotations

import streamlit as st

import config
from ingesta import plantillas
from ingesta.fuente import FuenteCSV, cargar_y_validar
from modelo.motor import motores_disponibles
from persistencia import db, historico, previsiones
from ui import servicios
from ui.sidebar import Seleccion
import recalcular as recalc


def _seccion_plantillas() -> None:
    st.subheader("1 · Descargar plantilla")
    st.caption("Descarga el formato exacto para rellenar tus datos (agregados por centro/turno/mes).")
    c1, c2 = st.columns(2)
    c1.download_button(
        "⬇️ Plantilla de absentismo (CSV)",
        data=plantillas.plantilla_absentismo_csv(),
        file_name="plantilla_absentismo.csv", mime="text/csv",
    )
    c2.download_button(
        "⬇️ Plantilla de gripe — opcional (CSV)",
        data=plantillas.plantilla_gripe_csv(),
        file_name="plantilla_gripe.csv", mime="text/csv",
    )


def _seccion_subida(sel: Seleccion) -> None:
    st.subheader("2 · Subir datos (modo real)")
    if sel.modo != "real":
        st.info(
            "Estás en **modo prueba**. Para cargar tus propios datos, cambia a "
            "**modo real** en la barra lateral. Aquí puedes practicar igualmente: "
            "la validación funciona en ambos modos."
        )

    f_abs = st.file_uploader(
        "Fichero de absentismo (CSV o Excel)", type=["csv", "xlsx", "xls"], key="up_abs"
    )
    f_gripe = st.file_uploader(
        "Fichero de gripe — opcional (CSV o Excel)", type=["csv", "xlsx", "xls"], key="up_gripe"
    )

    if f_abs is None:
        return

    fuente = FuenteCSV(absentismo=f_abs, gripe=f_gripe)
    res_abs, res_gripe = cargar_y_validar(fuente)

    # --- Mostrar validación ---
    if res_abs.columnas_personales:
        st.error(res_abs.errores[0])
        st.stop()
    for e in res_abs.errores:
        st.error(e)
    for a in res_abs.avisos:
        st.warning(a)

    if not res_abs.ok:
        st.info("Corrige los errores y vuelve a subir el fichero.")
        return

    st.success(f"✅ Validación correcta: {res_abs.n_filas} filas listas para cargar.")
    st.dataframe(res_abs.df.head(20), hide_index=True, use_container_width=True)
    if res_gripe is not None:
        if res_gripe.ok:
            st.success(f"✅ Fichero de gripe válido ({res_gripe.n_filas} filas).")
        else:
            for e in res_gripe.errores:
                st.error(f"Gripe: {e}")

    # --- Confirmar carga (solo en modo real; escribe en la base real) ---
    if sel.modo == "real":
        if st.button("💾 Confirmar carga en modo real", type="primary"):
            df = res_abs.df.rename(columns={"plantilla_media": "plantilla"})[
                ["centro", "turno", "periodo", "tasa", "jornadas_perdidas", "plantilla"]
            ]
            n = historico.guardar_historico(df, modo="real")
            if res_gripe is not None and res_gripe.ok:
                st.session_state["gripe_real"] = res_gripe.df
            st.success(f"Guardadas {n} filas en el histórico real. Ahora pulsa **Recalcular**.")
    else:
        st.caption("En modo prueba la carga no se guarda (los datos son de práctica).")


def _seccion_recalcular(sel: Seleccion) -> None:
    st.subheader("3 · Recalcular previsión")
    st.caption(
        "El recálculo **no** ocurre al abrir la app: se lanza aquí (o como job en el "
        "futuro). Cada recálculo crea una **tanda nueva** y NUNCA sobrescribe las anteriores."
    )

    motores = motores_disponibles()
    motor = st.selectbox("Motor de previsión", options=motores, index=0,
                         help="Prophet (si está disponible) es el principal; SARIMA la alternativa.")
    if "prophet" not in motores:
        st.caption("ℹ️ Prophet no está disponible en este entorno; se ofrecen los demás motores.")

    if st.button("🔄 Recalcular previsión", type="primary"):
        gripe_df = st.session_state.get("gripe_real") if sel.modo == "real" else None
        with st.spinner("Calculando previsión para todos los centros y turnos…"):
            res = recalc.recalcular(
                modo=sel.modo, motor=motor,
                horizonte=max(config.PARAMS_MODELO.horizontes_meses), gripe_df=gripe_df,
            )
        if res.id_ejecucion:
            st.success(res.mensaje)
        else:
            st.warning(res.mensaje)
        for a in res.avisos:
            st.warning(a)


def _seccion_estado(sel: Seleccion) -> None:
    st.subheader("Estado actual de los datos")
    hist = servicios.historico_de(sel.modo)
    ejec = previsiones.listar_ejecuciones(modo=sel.modo)
    c1, c2, c3 = st.columns(3)
    c1.metric("Filas de histórico", servicios.fmt_num(len(hist)))
    c2.metric("Centros", servicios.fmt_num(hist["centro"].nunique() if not hist.empty else 0))
    c3.metric("Tandas de previsión", servicios.fmt_num(len(ejec)))
    if not ejec.empty:
        st.caption(f"Última tanda: {ejec.iloc[0]['fecha_calculo']} · modelo {ejec.iloc[0]['modelo']}")

    st.caption(f"Almacenamiento: {db.describe_backend(sel.modo)}")
    if st.button("🔌 Probar conexión con el almacenamiento"):
        ok, msg = db.probar_conexion(sel.modo)
        (st.success if ok else st.error)(msg)


def render(sel: Seleccion) -> None:
    st.header("🗂️ Datos")
    _seccion_plantillas()
    st.divider()
    _seccion_subida(sel)
    st.divider()
    _seccion_recalcular(sel)
    st.divider()
    _seccion_estado(sel)
