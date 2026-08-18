"""
ui/sidebar.py — Barra lateral común a todas las páginas.

Contiene el selector de MODO (prueba/real) bien visible, y los selectores de
centro, turno, horizonte (3/6 meses) y la fecha de análisis ("ver la foto a
fecha…"). Devuelve la selección como un objeto para que las páginas la usen.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import streamlit as st

import config
from persistencia import db
from ui import servicios


@dataclass
class Seleccion:
    modo: str                 # 'prueba' | 'real'
    centro: str | None
    turno: str | None
    horizonte: int            # 3 o 6
    fecha_analisis: date


def construir_sidebar() -> Seleccion:
    st.sidebar.title("Absentismo · Previsión")

    # --- Selector de MODO (por defecto: prueba) ---
    modo_label = st.sidebar.radio(
        "Modo de datos",
        options=["Prueba (datos ficticios)", "Real (mis datos)"],
        index=0 if config.MODO_POR_DEFECTO == "prueba" else 1,
        help="El modo prueba genera datos sintéticos; el modo real usa tus datos cargados.",
    )
    modo = "prueba" if modo_label.startswith("Prueba") else "real"

    # En modo prueba, sembramos datos + primera previsión si hace falta.
    if modo == "prueba":
        servicios.asegurar_datos_demo()
    else:
        servicios.inicializar("real")

    # --- Centro y turno (dependientes de los datos disponibles) ---
    centros = servicios.centros_de(modo)
    if centros:
        centro = st.sidebar.selectbox("Centro de trabajo", options=centros)
        turnos = servicios.turnos_de(modo, centro)
        turno = st.sidebar.selectbox(
            "Turno", options=turnos, format_func=servicios.turno_bonito
        )
    else:
        centro, turno = None, None
        st.sidebar.info("No hay datos cargados en este modo. Ve a la página **Datos**.")

    # --- Horizonte ---
    horizonte = st.sidebar.radio(
        "Horizonte de previsión", options=list(config.PARAMS_MODELO.horizontes_meses),
        index=len(config.PARAMS_MODELO.horizontes_meses) - 1,
        format_func=lambda m: f"{m} meses", horizontal=True,
    )

    # --- Fecha de análisis ("ver la foto a fecha…") ---
    fecha_analisis = st.sidebar.date_input(
        "Ver la foto a fecha…", value=date.today(), format="DD/MM/YYYY",
        help="Lee la previsión que ya estaba guardada a esa fecha (no recalcula al vuelo).",
    )

    # --- Info del backend de persistencia ---
    st.sidebar.divider()
    st.sidebar.caption(f"Almacenamiento: {db.describe_backend(modo)}")

    return Seleccion(
        modo=modo, centro=centro, turno=turno,
        horizonte=int(horizonte), fecha_analisis=fecha_analisis,
    )


def banner_modo(modo: str) -> None:
    """Muestra un banner bien visible del modo actual en la parte superior."""
    if modo == "prueba":
        st.warning(
            "🧪 **MODO PRUEBA** — datos ficticios generados automáticamente. "
            "Nada de lo que ves aquí son datos reales.",
            icon="🧪",
        )
    else:
        st.success("📁 **MODO REAL** — usando los datos que has cargado.", icon="📁")
