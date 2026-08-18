"""
ui/servicios.py — Servicios compartidos por las páginas de la interfaz.

Centraliza el acceso a datos según el modo (prueba/real), la siembra del modo
prueba (datos sintéticos + primera tanda de previsión) y el formato español de
números, porcentajes y fechas.
"""
from __future__ import annotations

import io
import math

import pandas as pd

import config
from persistencia import db, historico, previsiones


# ---------------------------------------------------------------------------
# Acceso a datos según modo
# ---------------------------------------------------------------------------
def inicializar(modo: str) -> None:
    """Crea el esquema de la base del modo indicado."""
    db.inicializar_esquema(modo)


def asegurar_datos_demo() -> None:
    """Siembra el modo prueba si está vacío: histórico sintético + 1ª previsión.

    Es idempotente: si ya hay datos y una tanda de previsión, no hace nada.
    """
    from datos_demo.generador import generar_historico_para_db
    from recalcular import recalcular

    db.inicializar_esquema(modo="prueba")
    if historico.leer_historico(modo="prueba").empty:
        historico.guardar_historico(generar_historico_para_db(), modo="prueba")
    if previsiones.listar_ejecuciones(modo="prueba").empty:
        from modelo.motor import mejor_motor_disponible
        recalcular(modo="prueba", motor=mejor_motor_disponible())


def historico_de(modo: str, centro: str | None = None, turno: str | None = None) -> pd.DataFrame:
    return historico.leer_historico(centro=centro, turno=turno, modo=modo)


def centros_de(modo: str) -> list[str]:
    return historico.listar_centros(modo=modo)


def turnos_de(modo: str, centro: str | None = None) -> list[str]:
    return historico.listar_turnos(centro=centro, modo=modo)


def hay_datos(modo: str) -> bool:
    return not historico.leer_historico(modo=modo).empty


# ---------------------------------------------------------------------------
# Formato español
# ---------------------------------------------------------------------------
def _es(numero: str) -> str:
    """Convierte el formato anglosajón '1,234.5' al español '1.234,5'."""
    return numero.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_num(x: float | int | None, dec: int = 0) -> str:
    """Número con separador de miles '.' y decimal ',' (formato español)."""
    if x is None or pd.isna(x):
        return "—"
    return _es(f"{x:,.{dec}f}")


def fmt_pct(x: float | None, dec: int = 1) -> str:
    """Tasa (0–1) como porcentaje español, p. ej. 0.0821 → '8,2 %'."""
    if x is None or pd.isna(x):
        return "—"
    return _es(f"{x * 100:,.{dec}f}") + " %"


def fmt_fecha(ts) -> str:
    """Fecha en formato español dd/mm/aaaa."""
    ts = pd.Timestamp(ts)
    return ts.strftime("%d/%m/%Y")


def jornadas_teoricas_ref(hist_ct: pd.DataFrame) -> tuple[dict[int, float], float]:
    """Estima jornadas teóricas por mes del año a partir del histórico.

    La tabla `historico` guarda jornadas_perdidas y tasa, así que las teóricas se
    derivan como perdidas/tasa. Devuelve (dict mes→teóricas medias, media global),
    para poder convertir una tasa prevista en jornadas perdidas previstas.
    """
    df = hist_ct.copy()
    df = df[(df["tasa"] > 0) & df["jornadas_perdidas"].notna()]
    if df.empty:
        return {}, float("nan")
    df["teoricas"] = df["jornadas_perdidas"] / df["tasa"]
    df["mes"] = df["periodo"].str[5:7].astype(int)
    por_mes = df.groupby("mes")["teoricas"].mean().to_dict()
    return por_mes, float(df["teoricas"].mean())


def periodo_bonito(periodo: str) -> str:
    """'2026-01' → 'ene 2026'."""
    meses = ["ene", "feb", "mar", "abr", "may", "jun",
             "jul", "ago", "sep", "oct", "nov", "dic"]
    anio, mes = periodo.split("-")
    return f"{meses[int(mes) - 1]} {anio}"


# Etiquetas de turno para MOSTRAR (el valor interno sigue siendo 'manana', etc.).
ETIQUETAS_TURNO: dict[str, str] = {
    "manana": "Mañana", "tarde": "Tarde", "noche": "Noche", "todos": "Todos",
}


def turno_bonito(turno: str) -> str:
    """'manana' → 'Mañana' (solo para presentación)."""
    return ETIQUETAS_TURNO.get(turno, str(turno).capitalize())


# ---------------------------------------------------------------------------
# Dimensionamiento de plantilla y semáforo
# ---------------------------------------------------------------------------
def plantilla_ref(hist_ct: pd.DataFrame) -> float:
    """Plantilla de referencia para un centro×turno: la del último mes conocido."""
    df = hist_ct.dropna(subset=["plantilla"])
    if df.empty:
        return float("nan")
    df = df.sort_values("periodo")
    return float(df["plantilla"].iloc[-1])


def fte_ausentes(tasa: float, plantilla: float) -> float:
    """Personas equivalentes ausentes (FTE) = tasa × plantilla."""
    if plantilla is None or pd.isna(plantilla):
        return float("nan")
    return float(tasa) * float(plantilla)


def refuerzo_recomendado(tasa_hi: float, plantilla: float) -> int:
    """Personas de refuerzo para cubrir el peor caso del intervalo 90% (redondeo arriba)."""
    fte = fte_ausentes(tasa_hi, plantilla)
    if pd.isna(fte):
        return 0
    return int(math.ceil(fte))


def clasificar_semaforo(tasa: float) -> tuple[str, str]:
    """Devuelve (emoji, nivel) según los umbrales de config: verde/ámbar/rojo."""
    u = config.UMBRALES_SEMAFORO
    if pd.isna(tasa):
        return "⚪", "sin dato"
    if tasa < u.verde_max:
        return "🟢", "verde"
    if tasa <= u.ambar_max:
        return "🟡", "ambar"
    return "🔴", "rojo"


def fiabilidad_de(hist_ct: pd.DataFrame) -> str:
    """'alta' si hay >= min_meses_fiable meses; si no 'baja'."""
    n = hist_ct["periodo"].nunique()
    return "alta" if n >= config.PARAMS_MODELO.min_meses_fiable else "baja"


# ---------------------------------------------------------------------------
# Exportación a Excel / CSV
# ---------------------------------------------------------------------------
def construir_excel(hojas: dict[str, pd.DataFrame]) -> bytes:
    """Empaqueta varios DataFrames en un Excel (una hoja por clave) y lo devuelve en bytes."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for nombre, df in hojas.items():
            df.to_excel(writer, sheet_name=nombre[:31], index=False)
    return buffer.getvalue()


def a_csv_bytes(df: pd.DataFrame) -> bytes:
    """DataFrame a CSV en bytes (separador ';', UTF-8 con BOM para Excel español)."""
    return df.to_csv(index=False, sep=";").encode("utf-8-sig")
