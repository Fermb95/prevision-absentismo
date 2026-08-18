"""
ui/auth.py — Protección opcional por contraseña (sin sistema de usuarios).

Si la variable de entorno APP_PASSWORD está definida, se pide contraseña antes
de mostrar la app. Si no lo está, la app queda abierta. No hay roles ni cuentas:
es una barrera simple para un enlace compartido.
"""
from __future__ import annotations

import streamlit as st

import config


def exigir_password() -> None:
    """Bloquea la app hasta introducir la contraseña, si APP_PASSWORD está definida."""
    if not config.APP_PASSWORD:
        return  # app abierta
    if st.session_state.get("_auth_ok"):
        return

    st.title("🔒 Acceso restringido")
    st.caption("Introduce la contraseña para ver la previsión de absentismo.")
    pwd = st.text_input("Contraseña", type="password")
    if pwd:
        if pwd == config.APP_PASSWORD:
            st.session_state["_auth_ok"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
    st.stop()
