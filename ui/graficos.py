"""
ui/graficos.py — Gráficos Plotly reutilizables.

Convención: el eje Y es la TASA (fracción 0–1) mostrada como porcentaje. El eje X
es temporal, con etiquetas de mes en ESPAÑOL. Se resaltan los meses de invierno
(gripe) y se marca "HOY". La barra de herramientas de Plotly (en inglés) se
oculta desde las llamadas a st.plotly_chart con CONFIG_PLOTLY.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

# Configuración para st.plotly_chart: sin barra en inglés, aspecto limpio.
CONFIG_PLOTLY = {"displayModeBar": False, "locale": "es"}

_AZUL = "#2563eb"
_NARANJA = "#ea580c"
_BANDA = "rgba(37,99,235,0.14)"
_GRIPE = "rgba(234,88,12,0.07)"
_VERDE = "#16a34a"

_MESES = ["ene", "feb", "mar", "abr", "may", "jun",
          "jul", "ago", "sep", "oct", "nov", "dic"]


def _ts(periodos: pd.Series | list[str]) -> list[pd.Timestamp]:
    return [pd.Timestamp(int(p[:4]), int(p[5:7]), 1) for p in periodos]


def _etiqueta_mes(ts: pd.Timestamp) -> str:
    return f"{_MESES[ts.month - 1]} {ts.year}"


def _aplicar_ticks_es(fig: go.Figure, todos_ts: list[pd.Timestamp]) -> None:
    """Fija etiquetas de mes en español, mostrando ~8 marcas como mucho."""
    if not todos_ts:
        return
    ordenados = sorted(set(todos_ts))
    paso = max(1, len(ordenados) // 8)
    marcas = ordenados[::paso]
    fig.update_xaxes(
        tickmode="array",
        tickvals=marcas,
        ticktext=[_etiqueta_mes(t) for t in marcas],
    )


def _sombrea_gripe(fig: go.Figure, inicio: pd.Timestamp, fin: pd.Timestamp) -> None:
    """Franjas verticales tenues en los inviernos del rango [inicio, fin]."""
    for anio in range(inicio.year - 1, fin.year + 1):
        x0 = pd.Timestamp(anio, 12, 1)
        x1 = pd.Timestamp(anio + 1, 3, 1)
        if x1 < inicio or x0 > fin:
            continue
        fig.add_vrect(x0=max(x0, inicio), x1=min(x1, fin),
                      fillcolor=_GRIPE, line_width=0, layer="below")


def _layout_es(fig: go.Figure, titulo: str) -> go.Figure:
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=17)),
        template="plotly_white",
        height=440,
        margin=dict(l=10, r=10, t=54, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
        font=dict(family="Inter, Segoe UI, system-ui, sans-serif", color="#111827"),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_yaxes(title="Tasa de absentismo", tickformat=".0%", rangemode="tozero",
                     gridcolor="#eef1f5")
    fig.update_xaxes(title="", gridcolor="#eef1f5")
    return fig


def grafico_prevision(
    hist_ct: pd.DataFrame,
    prev_ct: pd.DataFrame,
    titulo: str = "Previsión de absentismo",
) -> go.Figure:
    """Histórico (sólido) + previsión (discontinua) + banda 90% + HOY + gripe."""
    fig = go.Figure()

    hist = hist_ct.sort_values("periodo")
    x_hist = _ts(hist["periodo"].tolist())
    x_prev = _ts(prev_ct["periodo_objetivo"].tolist())

    if not prev_ct.empty:
        fig.add_trace(go.Scatter(
            x=x_prev + x_prev[::-1],
            y=prev_ct["hi"].tolist() + prev_ct["lo"].tolist()[::-1],
            fill="toself", fillcolor=_BANDA, line=dict(width=0),
            name="Intervalo 90 %", hoverinfo="skip",
        ))

    fig.add_trace(go.Scatter(
        x=x_hist, y=hist["tasa"], mode="lines+markers",
        line=dict(color=_AZUL, width=2.6), marker=dict(size=5), name="Histórico",
    ))

    if not prev_ct.empty:
        x_union = ([x_hist[-1]] + x_prev) if x_hist else x_prev
        y_union = ([hist["tasa"].iloc[-1]] + prev_ct["valor"].tolist()) if x_hist \
            else prev_ct["valor"].tolist()
        fig.add_trace(go.Scatter(
            x=x_union, y=y_union, mode="lines+markers",
            line=dict(color=_NARANJA, width=2.6, dash="dash"), marker=dict(size=5),
            name="Previsión",
        ))

    todos_x = x_hist + x_prev
    if todos_x:
        _sombrea_gripe(fig, min(todos_x), max(todos_x))
    fig.add_vline(x=pd.Timestamp.today().normalize(), line_width=2,
                  line_dash="dot", line_color="#9aa4b2")
    fig.add_annotation(x=pd.Timestamp.today().normalize(), y=1, yref="paper",
                       text="HOY", showarrow=False, font=dict(color="#9aa4b2", size=11),
                       yshift=8)
    _layout_es(fig, titulo)
    _aplicar_ticks_es(fig, todos_x)
    return fig


def grafico_precision(
    prev_pasada: pd.DataFrame,
    titulo: str = "Previsión de entonces frente a la realidad",
) -> go.Figure:
    """Previsión generada 'por aquel entonces' (con banda) contra lo REAL ocurrido."""
    fig = go.Figure()
    x = _ts(prev_pasada["periodo_objetivo"].tolist())

    fig.add_trace(go.Scatter(
        x=x + x[::-1],
        y=prev_pasada["hi"].tolist() + prev_pasada["lo"].tolist()[::-1],
        fill="toself", fillcolor=_BANDA, line=dict(width=0),
        name="Intervalo 90 %", hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=prev_pasada["valor"], mode="lines+markers",
        line=dict(color=_NARANJA, width=2.6, dash="dash"), name="Lo que preveíamos",
    ))
    if "real" in prev_pasada.columns and prev_pasada["real"].notna().any():
        fig.add_trace(go.Scatter(
            x=x, y=prev_pasada["real"], mode="lines+markers",
            line=dict(color=_VERDE, width=2.6), name="Lo que ocurrió",
        ))
    if x:
        _sombrea_gripe(fig, min(x), max(x))
    _layout_es(fig, titulo)
    _aplicar_ticks_es(fig, x)
    return fig


def grafico_comparativa(
    hist_ct: pd.DataFrame,
    prev_nueva: pd.DataFrame,
    prev_antigua: pd.DataFrame,
    etiqueta_nueva: str,
    etiqueta_antigua: str,
    titulo: str = "Comparativa de previsiones",
) -> go.Figure:
    """Histórico + dos previsiones (dos tandas distintas) superpuestas para comparar."""
    fig = go.Figure()
    hist = hist_ct.sort_values("periodo")
    x_hist = _ts(hist["periodo"].tolist())

    fig.add_trace(go.Scatter(
        x=x_hist, y=hist["tasa"], mode="lines+markers",
        line=dict(color=_AZUL, width=2.4), marker=dict(size=4), name="Histórico",
    ))
    # Previsión anterior (gris) y nueva (naranja) para ver el cambio.
    if not prev_antigua.empty:
        fig.add_trace(go.Scatter(
            x=_ts(prev_antigua["periodo_objetivo"].tolist()), y=prev_antigua["valor"],
            mode="lines+markers", line=dict(color="#94a3b8", width=2.4, dash="dot"),
            name=f"Anterior ({etiqueta_antigua})",
        ))
    if not prev_nueva.empty:
        fig.add_trace(go.Scatter(
            x=_ts(prev_nueva["periodo_objetivo"].tolist()), y=prev_nueva["valor"],
            mode="lines+markers", line=dict(color=_NARANJA, width=2.8, dash="dash"),
            name=f"Nueva ({etiqueta_nueva})",
        ))

    todos = x_hist + _ts(prev_nueva["periodo_objetivo"].tolist())
    if todos:
        _sombrea_gripe(fig, min(todos), max(todos))
    _layout_es(fig, titulo)
    _aplicar_ticks_es(fig, todos)
    return fig
