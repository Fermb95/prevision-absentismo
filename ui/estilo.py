"""
ui/estilo.py — Identidad visual corporativa HEFAME + utilidades de estilo.

Colores corporativos (tomados de hefame.es): amarillo #FACD01 y negro sobre
blanco. El logo HEFAME se muestra SIEMPRE visible: en la cabecera (panel
amarillo) y fijo arriba en la barra lateral.

Si existe el fichero `ui/assets/hefame.png`, se usa esa imagen como logo; si no,
se dibuja el wordmark "HEFAME" con tipografía (negrita cursiva), para que la app
funcione igual sin depender del fichero.
"""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

# --- Paleta corporativa HEFAME ---
AMARILLO = "#FACD01"
NEGRO = "#111111"
# Colores de dato (semáforo) — se mantienen por significado.
VERDE = "#16a34a"
AMBAR = "#d97706"
ROJO = "#dc2626"
TENUE = "#5f6470"

_ASSET_LOGO = Path(__file__).parent / "assets" / "hefame.png"


def _logo_html(alto_px: int) -> str:
    """Devuelve el HTML del logo: imagen oficial si existe, si no el wordmark."""
    if _ASSET_LOGO.exists():
        b64 = base64.b64encode(_ASSET_LOGO.read_bytes()).decode()
        return (
            f'<img src="data:image/png;base64,{b64}" alt="HEFAME" '
            f'style="height:{alto_px}px;display:block;" />'
        )
    return (
        f'<span style="font-family:Arial,Helvetica,sans-serif;font-weight:900;'
        f'font-style:italic;font-size:{alto_px}px;line-height:1;letter-spacing:-.03em;'
        f'color:{NEGRO};">HEFAME</span>'
    )


_CSS = f"""
<style>
:root {{
  --amarillo: {AMARILLO};
  --negro: {NEGRO};
  --fondo: #f6f6f3;
  --tarjeta: #ffffff;
  --texto: {NEGRO};
  --tenue: {TENUE};
  --borde: #e7e7e2;
}}

html, body, [class*="css"] {{
  font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
}}
.stApp {{ background: var(--fondo); }}

/* Ocultar la fontanería en inglés de Streamlit */
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {{
  visibility: hidden; height: 0; position: fixed;
}}
#MainMenu {{ visibility: hidden; }}
header {{ background: transparent !important; }}
footer {{ visibility: hidden; height: 0; }}
.block-container {{ padding-top: 1.1rem; padding-bottom: 3rem; max-width: 1200px; }}

h1, h2, h3 {{ color: var(--texto); font-weight: 700; letter-spacing: -0.01em; }}

/* --- Cabecera: panel amarillo corporativo con logo --- */
.cabecera {{
  background: var(--amarillo);
  border-radius: 16px; padding: 16px 24px; margin-bottom: 18px;
  display: flex; align-items: center; justify-content: space-between;
  gap: 18px; flex-wrap: wrap;
  box-shadow: 0 4px 16px rgba(0,0,0,.12);
  border: 1px solid rgba(0,0,0,.08);
}}
.cabecera .marca {{ display: flex; align-items: center; gap: 18px; }}
.cabecera .separador {{ width: 2px; height: 42px; background: rgba(0,0,0,.22); }}
.cabecera .titulo {{ font-size: 1.25rem; font-weight: 800; color: #111; letter-spacing: -.02em; }}
.cabecera .subtitulo {{ color: #2b2b2b; font-size: .88rem; margin-top: 1px; }}
.pildora {{
  display: inline-flex; align-items: center; gap: 8px;
  padding: 8px 14px; border-radius: 999px; font-weight: 700; font-size: .82rem;
  background: {NEGRO}; color: #fff; border: 1px solid rgba(0,0,0,.2);
}}

/* --- Logo fijo en la barra lateral --- */
.logo-sidebar {{
  background: var(--amarillo); border-radius: 12px; padding: 14px 10px;
  text-align: center; margin: -8px 0 10px 0; border: 1px solid rgba(0,0,0,.08);
}}

/* --- KPIs como tarjetas con acento amarillo --- */
[data-testid="stMetric"] {{
  background: var(--tarjeta); border: 1px solid var(--borde);
  border-left: 4px solid var(--amarillo);
  border-radius: 14px; padding: 16px 18px;
  box-shadow: 0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.06);
  transition: box-shadow .15s ease, transform .15s ease;
}}
[data-testid="stMetric"]:hover {{ box-shadow: 0 6px 16px rgba(0,0,0,.10); transform: translateY(-1px); }}
[data-testid="stMetricLabel"] p {{ font-weight: 600; color: var(--tenue); font-size: .82rem; }}
[data-testid="stMetricValue"] {{ color: var(--texto); font-weight: 700; }}

/* --- Barra lateral --- */
[data-testid="stSidebar"] {{ background: #ffffff; border-right: 1px solid var(--borde); }}

/* --- Botones (negro con hover amarillo corporativo) --- */
.stButton > button, .stDownloadButton > button {{
  border-radius: 10px; font-weight: 600; border: 1px solid var(--borde);
  transition: all .15s ease;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
  border-color: var(--negro); background: var(--amarillo); color: var(--negro);
}}
.stButton > button[kind="primary"] {{ background: var(--negro); border-color: var(--negro); color: #fff; }}
.stButton > button[kind="primary"]:hover {{ background: var(--amarillo); color: var(--negro); }}

/* --- Pestañas --- */
.stTabs [data-baseweb="tab-list"] {{ gap: 6px; }}
.stTabs [data-baseweb="tab"] {{ border-radius: 10px 10px 0 0; font-weight: 600; }}
.stTabs [aria-selected="true"] {{ box-shadow: inset 0 -3px 0 var(--amarillo); }}

/* --- Tablas --- */
[data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; border: 1px solid var(--borde); }}

/* --- Cargador de ficheros en español --- */
[data-testid="stFileUploaderDropzoneInstructions"] span {{ display: none; }}
[data-testid="stFileUploaderDropzoneInstructions"] > div::before {{
  content: "Arrastra el fichero aquí"; font-weight: 600; color: var(--texto);
}}
[data-testid="stFileUploaderDropzoneInstructions"] small {{ display: none; }}
[data-testid="stFileUploaderDropzoneInstructions"] > div::after {{
  content: "Límite 200 MB · CSV, XLSX o XLS"; font-size: .78rem; color: var(--tenue);
  display: block; margin-top: 2px;
}}

/* --- Alerta roja suave --- */
.alerta-roja {{
  background: #fef2f2; border: 1px solid #fecaca; color: #991b1b;
  border-radius: 14px; padding: 14px 16px; margin-bottom: 8px; font-weight: 500;
}}
</style>
"""


def aplicar_estilo() -> None:
    """Inyecta la hoja de estilo corporativa. Llamar una vez al inicio."""
    st.markdown(_CSS, unsafe_allow_html=True)


def logo_sidebar() -> None:
    """Dibuja el logo HEFAME fijo arriba de la barra lateral (siempre visible)."""
    st.sidebar.markdown(
        f'<div class="logo-sidebar">{_logo_html(26)}</div>', unsafe_allow_html=True
    )


def cabecera(modo: str, subtitulo: str = "Previsión de absentismo por centro de trabajo") -> None:
    """Cabecera: panel amarillo con logo HEFAME, título y píldora de modo."""
    pill = (
        '🧪 Modo prueba · datos ficticios' if modo == "prueba"
        else '📁 Modo real · tus datos'
    )
    st.markdown(
        f"""
        <div class="cabecera">
          <div class="marca">
            {_logo_html(30)}
            <div class="separador"></div>
            <div>
              <div class="titulo">Absentismo · Previsión</div>
              <div class="subtitulo">{subtitulo}</div>
            </div>
          </div>
          <span class="pildora">{pill}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
