"""
ingesta/validacion.py — Validación de ficheros subidos.

Dos cometidos:
  1. BARRERA DE PRIVACIDAD (innegociable): si el fichero contiene columnas que
     parezcan individuales (nombre, dni, edad, sexo, email, id_empleado...), la
     carga se RECHAZA con un mensaje claro. Solo se admiten datos agregados.
  2. Validación de esquema/tipos y normalización: comprueba columnas, tipos y
     rangos, calcula la tasa (o usa la columna `tasa` si viene) y deja el
     DataFrame listo para persistir, además de una lista de errores y avisos
     para mostrar en la vista previa.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import pandas as pd

import config


# ---------------------------------------------------------------------------
# Resultado estructurado (para pintar la vista previa en la interfaz)
# ---------------------------------------------------------------------------
@dataclass
class ResultadoValidacion:
    ok: bool
    errores: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    columnas_personales: list[str] = field(default_factory=list)
    df: pd.DataFrame | None = None      # normalizado, solo si ok
    n_filas: int = 0


# ---------------------------------------------------------------------------
# Utilidades de normalización de texto
# ---------------------------------------------------------------------------
def _normaliza(texto: str) -> str:
    """minúsculas, sin acentos, sin espacios extremos. Para comparar nombres."""
    txt = str(texto).replace("﻿", "")  # quita BOM que Excel pueda dejar
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return txt.strip().lower()


def _tokens(nombre_col: str) -> list[str]:
    """Parte un nombre de columna en tokens alfanuméricos."""
    return [t for t in re.split(r"[^a-z0-9]+", _normaliza(nombre_col)) if t]


# Sinónimos aceptados para nombres de columna → nombre canónico.
_SINONIMOS: dict[str, str] = {
    "ano": "anio", "año": "anio", "year": "anio",
    "mes_num": "mes", "month": "mes",
    "plantilla": "plantilla_media", "plantilla_med": "plantilla_media",
    "j_teoricas": "jornadas_teoricas", "jornadas_teoricas_total": "jornadas_teoricas",
    "j_perdidas": "jornadas_perdidas",
}


# ---------------------------------------------------------------------------
# 1. Barrera de privacidad
# ---------------------------------------------------------------------------
def detectar_columnas_personales(columnas: list[str]) -> list[str]:
    """Devuelve las columnas que parecen individuales/sensibles.

    Coincidencia robusta: por token exacto (para siglas cortas como dni/nif/nie)
    y por subcadena para términos largos (p. ej. 'empleado' dentro de 'id_empleado').
    """
    sospechosas: list[str] = []
    for col in columnas:
        norm = _normaliza(col)
        toks = _tokens(col)
        for termino in config.COLUMNAS_PERSONALES_PROHIBIDAS:
            t = _normaliza(termino)
            # Token exacto siempre; subcadena solo para términos largos (>=5) para
            # no dar falsos positivos como 'edad' dentro de 'antiguedad'.
            if t in toks or (len(t) >= 5 and t in norm):
                sospechosas.append(col)
                break
    return sospechosas


# ---------------------------------------------------------------------------
# 2. Renombrado a nombres canónicos
# ---------------------------------------------------------------------------
def _canoniza_columnas(df: pd.DataFrame) -> pd.DataFrame:
    nuevo: dict[str, str] = {}
    for col in df.columns:
        norm = _normaliza(col).replace(" ", "_")
        norm = _SINONIMOS.get(norm, norm)
        nuevo[col] = norm
    return df.rename(columns=nuevo)


# ---------------------------------------------------------------------------
# 3. Validación del fichero principal de absentismo
# ---------------------------------------------------------------------------
def validar_absentismo(df_bruto: pd.DataFrame) -> ResultadoValidacion:
    """Valida y normaliza el fichero `absentismo_mensual`.

    Rechaza (ok=False) si hay columnas personales o faltan columnas/hay tipos
    inválidos. Si ok=True, `df` trae columnas normalizadas y la tasa calculada.
    """
    res = ResultadoValidacion(ok=False)

    if df_bruto is None or df_bruto.empty:
        res.errores.append("El fichero está vacío o no se pudo leer.")
        return res

    # --- BARRERA DE PRIVACIDAD (lo primero de todo) ---
    personales = detectar_columnas_personales(list(df_bruto.columns))
    if personales:
        res.columnas_personales = personales
        res.errores.append(
            "Carga RECHAZADA: el fichero contiene columnas que parecen datos "
            f"personales o de salud: {', '.join(personales)}. "
            "Esta aplicación solo admite datos AGREGADOS por centro/turno/mes. "
            "Elimina esas columnas y vuelve a subir el fichero."
        )
        return res  # no seguimos procesando datos personales

    df = _canoniza_columnas(df_bruto.copy())

    # --- Columnas mínimas ---
    faltan_clave = [c for c in ("centro", "turno", "anio", "mes") if c not in df.columns]
    if faltan_clave:
        res.errores.append(f"Faltan columnas obligatorias: {', '.join(faltan_clave)}.")

    tiene_tasa = config.COLUMNA_TASA_ALTERNATIVA in df.columns
    tiene_jornadas = "jornadas_teoricas" in df.columns and "jornadas_perdidas" in df.columns
    if not tiene_tasa and not tiene_jornadas:
        res.errores.append(
            "Debes aportar 'jornadas_teoricas' y 'jornadas_perdidas' para calcular "
            "la tasa, o bien una columna 'tasa' directa."
        )
    if res.errores:
        return res  # sin columnas base no tiene sentido seguir

    # --- Tipos numéricos ---
    for col in ("anio", "mes"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("plantilla_media", "jornadas_teoricas", "jornadas_perdidas"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if df["anio"].isna().any() or df["mes"].isna().any():
        res.errores.append("Hay valores no numéricos en 'anio' o 'mes'.")
        return res

    df["anio"] = df["anio"].astype(int)
    df["mes"] = df["mes"].astype(int)

    # --- Rangos ---
    if not df["mes"].between(1, 12).all():
        res.errores.append("La columna 'mes' debe estar entre 1 y 12.")
    if not df["anio"].between(2000, 2100).all():
        res.avisos.append("Hay años fuera del rango 2000–2100; revísalos.")

    # --- Turno válido ---
    df["turno"] = df["turno"].map(_normaliza)
    turnos_malos = sorted(set(df["turno"]) - set(config.TURNOS_VALIDOS))
    if turnos_malos:
        res.errores.append(
            f"Valores de 'turno' no válidos: {', '.join(turnos_malos)}. "
            f"Usa: {', '.join(config.TURNOS_VALIDOS)}."
        )

    # --- Cálculo / validación de la tasa ---
    if tiene_jornadas:
        neg = (df["jornadas_teoricas"] <= 0) | (df["jornadas_perdidas"] < 0)
        if neg.any():
            res.errores.append(
                "Hay 'jornadas_teoricas' <= 0 o 'jornadas_perdidas' < 0 (no válido)."
            )
        if (df["jornadas_perdidas"] > df["jornadas_teoricas"]).any():
            res.avisos.append(
                "En algunas filas las jornadas perdidas superan a las teóricas; "
                "revísalo (¿bajas largas o error de carga?)."
            )
        df["tasa"] = df["jornadas_perdidas"] / df["jornadas_teoricas"]
    else:
        df["tasa"] = pd.to_numeric(df[config.COLUMNA_TASA_ALTERNATIVA], errors="coerce")
        if df["tasa"].isna().any():
            res.errores.append("La columna 'tasa' tiene valores no numéricos.")
        elif df["tasa"].max() > 1.5:
            res.avisos.append(
                "La 'tasa' parecía venir en porcentaje (>1,5); se ha dividido entre 100."
            )
            df["tasa"] = df["tasa"] / 100.0

    if res.errores:
        return res

    # --- Duplicados centro/turno/anio/mes ---
    clave = ["centro", "turno", "anio", "mes"]
    dups = df.duplicated(subset=clave, keep=False)
    if dups.any():
        n = int(dups.sum())
        res.avisos.append(
            f"Hay {n} filas duplicadas por centro/turno/mes; se conservará la última."
        )
        df = df.drop_duplicates(subset=clave, keep="last")

    # --- Factores estructurales OPCIONALES (por centro/turno, agregados) ---
    factores_presentes = _validar_factores(df, res)

    # --- Micro-segmentación OPCIONAL (puesto + carga), por subgrupo agregado ---
    segmentacion_presentes = _validar_segmentacion(df, res)

    # --- Periodo y columnas de salida ---
    df["periodo"] = df["anio"].astype(str) + "-" + df["mes"].astype(str).str.zfill(2)
    if "plantilla_media" not in df.columns:
        df["plantilla_media"] = pd.NA
        res.avisos.append("No hay 'plantilla_media'; algunas métricas la usan (opcional).")
    if "jornadas_perdidas" not in df.columns:
        df["jornadas_perdidas"] = pd.NA
    if "jornadas_teoricas" not in df.columns:
        df["jornadas_teoricas"] = pd.NA

    if res.errores:
        return res

    columnas_salida = [
        "centro", "turno", "anio", "mes", "periodo",
        "plantilla_media", "jornadas_teoricas", "jornadas_perdidas", "tasa",
    ] + factores_presentes + segmentacion_presentes
    res.df = df[columnas_salida].sort_values(["centro", "turno", "anio", "mes"]).reset_index(drop=True)
    res.n_filas = len(res.df)
    res.ok = True
    return res


def _validar_factores(df: pd.DataFrame, res: ResultadoValidacion) -> list[str]:
    """Valida (si vienen) los factores estructurales por centro/turno.

    Modifica `df` in situ (normaliza tipo_horario, convierte numéricos) y añade
    errores/avisos a `res`. Devuelve la lista de columnas de factor presentes.
    """
    presentes = [c for c in config.COLUMNAS_FACTORES if c in df.columns]
    if not presentes:
        return []

    # tipo_horario: normalizar y validar contra el catálogo.
    if "tipo_horario" in presentes:
        df["tipo_horario"] = df["tipo_horario"].map(
            lambda v: _normaliza(v) if pd.notna(v) else v
        )
        malos = sorted(
            set(df["tipo_horario"].dropna()) - set(config.TIPOS_HORARIO)
        )
        if malos:
            res.errores.append(
                f"Valores de 'tipo_horario' no válidos: {', '.join(malos)}. "
                f"Usa: {', '.join(config.TIPOS_HORARIO)}."
            )

    # Factores numéricos: convertir y avisar si se salen de rango.
    for col, (lo, hi) in config.RANGOS_FACTORES.items():
        if col in presentes:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            fuera = df[col].dropna()
            if not fuera.between(lo, hi).all():
                res.avisos.append(
                    f"Algunos valores de '{col}' están fuera del rango esperado "
                    f"({lo:g}–{hi:g}); revísalos."
                )
    return presentes


def _validar_segmentacion(df: pd.DataFrame, res: ResultadoValidacion) -> list[str]:
    """Valida (si vienen) las columnas de micro-segmentación: puesto y carga.

    'puesto' es texto (rol/función). 'carga' es numérico (indicador de carga).
    Devuelve la lista de columnas presentes.
    """
    presentes: list[str] = []
    if config.COLUMNA_PUESTO in df.columns:
        df[config.COLUMNA_PUESTO] = (
            df[config.COLUMNA_PUESTO].astype("string").str.strip()
        )
        presentes.append(config.COLUMNA_PUESTO)
    if config.COLUMNA_CARGA in df.columns:
        df[config.COLUMNA_CARGA] = pd.to_numeric(df[config.COLUMNA_CARGA], errors="coerce")
        if df[config.COLUMNA_CARGA].isna().all():
            res.avisos.append("La columna 'carga' no tiene valores numéricos válidos.")
        presentes.append(config.COLUMNA_CARGA)
    return presentes


# ---------------------------------------------------------------------------
# 4. Validación del fichero opcional de gripe
# ---------------------------------------------------------------------------
def validar_gripe(df_bruto: pd.DataFrame) -> ResultadoValidacion:
    """Valida el regresor externo de gripe (anio, mes, incidencia)."""
    res = ResultadoValidacion(ok=False)
    if df_bruto is None or df_bruto.empty:
        res.errores.append("El fichero de gripe está vacío.")
        return res

    df = _canoniza_columnas(df_bruto.copy())
    faltan = [c for c in config.COLUMNAS_GRIPE if c not in df.columns]
    if faltan:
        res.errores.append(f"Al fichero de gripe le faltan columnas: {', '.join(faltan)}.")
        return res

    for col in config.COLUMNAS_GRIPE:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[list(config.COLUMNAS_GRIPE)].isna().any().any():
        res.errores.append("El fichero de gripe tiene valores no numéricos.")
        return res

    if not df["mes"].between(1, 12).all():
        res.errores.append("La columna 'mes' del fichero de gripe debe estar entre 1 y 12.")
        return res

    df["anio"] = df["anio"].astype(int)
    df["mes"] = df["mes"].astype(int)
    res.df = df[list(config.COLUMNAS_GRIPE)].reset_index(drop=True)
    res.n_filas = len(res.df)
    res.ok = True
    return res
