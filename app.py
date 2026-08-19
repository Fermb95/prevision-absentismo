"""
app.py — Punto de entrada de la aplicación Streamlit.

Configura la página, aplica el estilo global, la protección opcional por
contraseña, construye la barra lateral, muestra la cabecera con el modo y enruta
a cada página. La lógica vive en los módulos ingesta/modelo/persistencia/ui.

Ejecutar en local:   streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Previsión de absentismo",
    page_icon="📉",
    layout="wide",
    initial_sidebar_state="expanded",
)

from ui import (  # noqa: E402
    auth,
    estilo,
    pagina_comparativa,
    pagina_datos,
    pagina_factores,
    pagina_precision,
    pagina_prevision,
    pagina_resumen,
    pagina_segmentacion,
)
from ui.sidebar import construir_sidebar  # noqa: E402

PAGINAS = {
    "🗺️ Resumen": pagina_resumen.render,
    "📈 Previsión": pagina_prevision.render,
    "🎯 Precisión": pagina_precision.render,
    "🔀 Comparativa": pagina_comparativa.render,
    "🧭 Factores": pagina_factores.render,
    "🔬 Segmentación": pagina_segmentacion.render,
    "🗂️ Datos": pagina_datos.render,
}


def main() -> None:
    estilo.aplicar_estilo()
    auth.exigir_password()

    sel = construir_sidebar()

    st.sidebar.divider()
    eleccion = st.sidebar.radio("Página", options=list(PAGINAS.keys()))

    estilo.cabecera(sel.modo)
    try:
        PAGINAS[eleccion](sel)
    except Exception as exc:  # noqa: BLE001 — la navegación debe seguir viva
        st.error(
            "Se ha producido un error al mostrar esta página. La navegación sigue "
            "disponible en la barra lateral; prueba otra página o revisa los datos."
        )
        with st.expander("Detalles técnicos del error"):
            st.exception(exc)

    st.sidebar.divider()
    st.sidebar.caption(
        "Solo datos agregados por centro, turno y mes. La aplicación no almacena "
        "ni procesa datos de personas ni de salud."
    )


if __name__ == "__main__":
    main()
