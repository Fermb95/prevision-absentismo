"""
app.py — Punto de entrada de la aplicación Streamlit.

Solo se encarga de: configurar la página, aplicar la protección opcional por
contraseña, construir la barra lateral, mostrar el banner de modo y enrutar a
cada una de las tres páginas. La lógica vive en los módulos ingesta/modelo/
persistencia/ui; aquí no hay reglas de negocio.

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

from ui import auth, pagina_datos, pagina_precision, pagina_prevision  # noqa: E402
from ui.sidebar import banner_modo, construir_sidebar  # noqa: E402

PAGINAS = {
    "📈 Previsión": pagina_prevision.render,
    "🎯 Precisión": pagina_precision.render,
    "🗂️ Datos": pagina_datos.render,
}


def main() -> None:
    auth.exigir_password()

    sel = construir_sidebar()

    st.sidebar.divider()
    eleccion = st.sidebar.radio("Página", options=list(PAGINAS.keys()))

    banner_modo(sel.modo)
    PAGINAS[eleccion](sel)

    st.sidebar.divider()
    st.sidebar.caption(
        "Solo datos AGREGADOS por centro/turno/mes. La app no almacena ni procesa "
        "datos de personas ni de salud."
    )


if __name__ == "__main__":
    main()
