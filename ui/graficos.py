"""
ui/graficos.py — Gráficos Plotly reutilizables.

Convención: el eje Y es la TASA (fracción 0–1) mostrada como porcentaje. El eje X
es temporal. Se resaltan los meses de invierno (gripe) y se marca "HOY".
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

_AZUL = "#1f6feb"
_NARANJA = "#e8710a"
_BANDA = "rgba(31,111,235,0.15)"
_GRIPE = "rgba(232,113,10,0.08)"
_VERDE = "#2ea043"

# Meses de invierno a resaltar como "temporada de gripe".
_MESES_GRIPE = (12, 1, 2)


def _ts(periodos: pd.Series | list[str]) -> list[pd.Timestamp]:
    return [pd.Timestamp(int(p[:4]), int(p[5:7]), 1) for p in periodos]


def _sombrea_gripe(fig: go.Figure, inicio: pd.Timestamp, fin: pd.Timestamp) -> None:
    """Añade franjas verticales tenues en los inviernos del rango [inicio, fin]."""
    for anio in range(inicio.year - 1, fin.year + 1):
        # Diciembre(anio) → febrero(anio+1)
        x0 = pd.Timestamp(anio, 12, 1)
        x1 = pd.Timestamp(anio + 1, 3, 1)
        if x1 < inicio or x0 > fin:
            continue
        fig.add_vrect(x0=max(x0, inicio), x1=min(x1, fin),
                      fillcolor=_GRIPE, line_width=0, layer="below")


def _layout_es(fig: go.Figure, titulo: str) -> go.Figure:
    fig.update_layout(
        title=titulo,
        template="plotly_white",
        height=430,
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
    )
    fig.update_yaxes(title="Tasa de absentismo", tickformat=".0%", rangemode="tozero")
    fig.update_xaxes(title="")
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

    # Banda del intervalo (primero, para que quede por debajo).
    if not prev_ct.empty:
        fig.add_trace(go.Scatter(
            x=x_prev + x_prev[::-1],
            y=prev_ct["hi"].tolist() + prev_ct["lo"].tolist()[::-1],
            fill="toself", fillcolor=_BANDA, line=dict(width=0),
            name="Intervalo 90%", hoverinfo="skip",
        ))

    # Histórico (línea sólida).
    fig.add_trace(go.Scatter(
        x=x_hist, y=hist["tasa"], mode="lines+markers",
        line=dict(color=_AZUL, width=2.5), name="Histórico",
    ))

    # Previsión (línea discontinua). La unimos con el último punto histórico.
    if not prev_ct.empty:
        x_union = ([x_hist[-1]] + x_prev) if x_hist else x_prev
        y_union = ([hist["tasa"].iloc[-1]] + prev_ct["valor"].tolist()) if x_hist \
            else prev_ct["valor"].tolist()
        fig.add_trace(go.Scatter(
            x=x_union, y=y_union, mode="lines+markers",
            line=dict(color=_NARANJA, width=2.5, dash="dash"), name="Previsión",
        ))

    # Rango temporal y adornos.
    todos_x = x_hist + x_prev
    if todos_x:
        _sombrea_gripe(fig, min(todos_x), max(todos_x))
    fig.add_vline(x=pd.Timestamp.today().normalize(), line_width=2,
                  line_dash="dot", line_color="#888")
    fig.add_annotation(x=pd.Timestamp.today().normalize(), y=1, yref="paper",
                       text="HOY", showarrow=False, font=dict(color="#888", size=11),
                       yshift=8)
    return _layout_es(fig, titulo)


def grafico_precision(
    prev_pasada: pd.DataFrame,
    titulo: str = "Previsión de entonces vs. realidad",
) -> go.Figure:
    """Previsión generada 'por aquel entonces' (con banda) contra lo REAL ocurrido."""
    fig = go.Figure()
    x = _ts(prev_pasada["periodo_objetivo"].tolist())

    fig.add_trace(go.Scatter(
        x=x + x[::-1],
        y=prev_pasada["hi"].tolist() + prev_pasada["lo"].tolist()[::-1],
        fill="toself", fillcolor=_BANDA, line=dict(width=0),
        name="Intervalo 90%", hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=prev_pasada["valor"], mode="lines+markers",
        line=dict(color=_NARANJA, width=2.5, dash="dash"), name="Lo que preveíamos",
    ))
    if "real" in prev_pasada.columns and prev_pasada["real"].notna().any():
        fig.add_trace(go.Scatter(
            x=x, y=prev_pasada["real"], mode="lines+markers",
            line=dict(color=_VERDE, width=2.5), name="Lo que ocurrió",
        ))
    if x:
        _sombrea_gripe(fig, min(x), max(x))
    return _layout_es(fig, titulo)
