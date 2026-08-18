"""
ui/estilo.py — Estética global: hoja de estilo, cabecera y píldora de modo.

Inyecta CSS para un aspecto profesional (tarjetas, tipografía, sombras suaves),
oculta la fontanería en inglés de Streamlit (barra superior, menú, pie) y
traduce al español los textos del cargador de ficheros. También ofrece una
cabecera con degradado y una píldora de estado del modo.
"""
from __future__ import annotations

import streamlit as st

# Paleta central (coherente con config.toml y con los gráficos).
PRIMARIO = "#2563eb"
VERDE = "#16a34a"
AMBAR = "#d97706"
ROJO = "#dc2626"
TEXTO = "#111827"
TENUE = "#6b7280"

_CSS = f"""
<style>
:root {{
  --primario: {PRIMARIO};
  --fondo: #f4f6fa;
  --tarjeta: #ffffff;
  --texto: {TEXTO};
  --tenue: {TENUE};
  --borde: #e5e7eb;
}}

/* Tipografía y fondo general */
html, body, [class*="css"] {{
  font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
}}
.stApp {{ background: var(--fondo); }}

/* Ocultar la fontanería de Streamlit (todo en inglés) */
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {{
  visibility: hidden; height: 0; position: fixed;
}}
#MainMenu {{ visibility: hidden; }}
header {{ background: transparent !important; }}
footer {{ visibility: hidden; height: 0; }}

/* Contenedor principal más centrado y con aire */
.block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1200px; }}

/* Encabezados */
h1, h2, h3 {{ color: var(--texto); font-weight: 700; letter-spacing: -0.01em; }}

/* KPIs como tarjetas */
[data-testid="stMetric"] {{
  background: var(--tarjeta);
  border: 1px solid var(--borde);
  border-radius: 16px;
  padding: 16px 18px;
  box-shadow: 0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.06);
  transition: box-shadow .15s ease, transform .15s ease;
}}
[data-testid="stMetric"]:hover {{
  box-shadow: 0 4px 12px rgba(16,24,40,.10); transform: translateY(-1px);
}}
[data-testid="stMetricLabel"] p {{ font-weight: 600; color: var(--tenue); font-size: .82rem; }}
[data-testid="stMetricValue"] {{ color: var(--texto); font-weight: 700; }}

/* Barra lateral */
[data-testid="stSidebar"] {{
  background: #ffffff; border-right: 1px solid var(--borde);
}}
[data-testid="stSidebar"] .stRadio label, [data-testid="stSidebar"] label {{
  font-weight: 500;
}}

/* Botones */
.stButton > button, .stDownloadButton > button {{
  border-radius: 10px; font-weight: 600; border: 1px solid var(--borde);
  transition: all .15s ease;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
  border-color: var(--primario); color: var(--primario);
}}
.stButton > button[kind="primary"] {{
  background: var(--primario); border-color: var(--primario);
}}

/* Pestañas */
.stTabs [data-baseweb="tab-list"] {{ gap: 6px; }}
.stTabs [data-baseweb="tab"] {{
  border-radius: 10px 10px 0 0; font-weight: 600;
}}

/* Tablas / dataframes */
[data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; border: 1px solid var(--borde); }}

/* Cargador de ficheros: traducir el texto interno (en inglés por defecto) */
[data-testid="stFileUploaderDropzoneInstructions"] span {{ display: none; }}
[data-testid="stFileUploaderDropzoneInstructions"] > div::before {{
  content: "Arrastra el fichero aquí"; font-weight: 600; color: var(--texto);
}}
[data-testid="stFileUploaderDropzoneInstructions"] small {{ display: none; }}
[data-testid="stFileUploaderDropzoneInstructions"] > div::after {{
  content: "Límite 200 MB · CSV, XLSX o XLS"; font-size: .78rem; color: var(--tenue);
  display: block; margin-top: 2px;
}}

/* Cabecera propia */
.cabecera {{
  background: linear-gradient(100deg, #2563eb 0%, #1e40af 100%);
  color: #fff; border-radius: 18px; padding: 22px 26px; margin-bottom: 18px;
  box-shadow: 0 6px 20px rgba(37,99,235,.25);
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;
}}
.cabecera .titulo {{ font-size: 1.5rem; font-weight: 800; letter-spacing: -.02em; }}
.cabecera .subtitulo {{ opacity: .9; font-size: .92rem; margin-top: 2px; }}
.pildora {{
  display: inline-flex; align-items: center; gap: 8px;
  padding: 8px 14px; border-radius: 999px; font-weight: 700; font-size: .85rem;
  background: rgba(255,255,255,.18); color: #fff; border: 1px solid rgba(255,255,255,.35);
}}
.pildora.real {{ background: rgba(255,255,255,.22); }}

/* Aviso/tarjeta de alerta suave */
.alerta-roja {{
  background: #fef2f2; border: 1px solid #fecaca; color: #991b1b;
  border-radius: 14px; padding: 14px 16px; margin-bottom: 8px; font-weight: 500;
}}
</style>
"""


def aplicar_estilo() -> None:
    """Inyecta la hoja de estilo global. Llamar una vez al inicio."""
    st.markdown(_CSS, unsafe_allow_html=True)


def cabecera(modo: str, subtitulo: str = "Previsión de absentismo por centro de trabajo") -> None:
    """Cabecera con degradado, título y píldora de estado del modo."""
    if modo == "prueba":
        pill = '<span class="pildora">🧪 Modo prueba · datos ficticios</span>'
    else:
        pill = '<span class="pildora real">📁 Modo real · tus datos</span>'
    st.markdown(
        f"""
        <div class="cabecera">
          <div>
            <div class="titulo">📉 Absentismo · Previsión</div>
            <div class="subtitulo">{subtitulo}</div>
          </div>
          {pill}
        </div>
        """,
        unsafe_allow_html=True,
    )
