"""
ingesta/plantillas.py — Plantillas vacías descargables (formato exacto de carga).

Genera el CSV que el usuario descarga para saber qué columnas y formato usar.
Se usa separador ';' y codificación UTF-8 con BOM para que Excel en español lo
abra bien al hacer doble clic. El lector (`FuenteCSV`) autodetecta el separador,
así que el fichero devuelto por el usuario se leerá sin problemas.
"""
from __future__ import annotations

import pandas as pd

import config

SEPARADOR = ";"
CODIFICACION = "utf-8-sig"  # BOM para Excel español


def plantilla_absentismo_df() -> pd.DataFrame:
    """Plantilla del fichero principal con filas de ejemplo (3 turnos).

    Incluye las columnas de factores estructurales OPCIONALES (por centro/turno):
    tipo_horario, rotacion_pct, antiguedad_media, satisfaccion_media, jornada_media.
    Si no quieres usarlas, puedes borrar esas columnas.
    """
    filas = [
        {"centro": "Almacén Norte", "turno": "manana", "anio": 2026, "mes": 1,
         "plantilla_media": 27, "jornadas_teoricas": 540, "jornadas_perdidas": 38,
         "tipo_horario": "flexible", "rotacion_pct": 12, "antiguedad_media": 9.5,
         "satisfaccion_media": 7.8, "jornada_media": 160,
         "puesto": "Preparación", "carga": 62},
        {"centro": "Almacén Norte", "turno": "tarde", "anio": 2026, "mes": 1,
         "plantilla_media": 18, "jornadas_teoricas": 360, "jornadas_perdidas": 25,
         "tipo_horario": "fijo", "rotacion_pct": 18, "antiguedad_media": 7.0,
         "satisfaccion_media": 7.1, "jornada_media": 160,
         "puesto": "Preparación", "carga": 58},
        {"centro": "Almacén Norte", "turno": "noche", "anio": 2026, "mes": 1,
         "plantilla_media": 12, "jornadas_teoricas": 240, "jornadas_perdidas": 26,
         "tipo_horario": "rotativo", "rotacion_pct": 34, "antiguedad_media": 4.5,
         "satisfaccion_media": 6.2, "jornada_media": 160,
         "puesto": "Preparación", "carga": 71},
    ]
    columnas = (
        list(config.COLUMNAS_ABSENTISMO)
        + list(config.COLUMNAS_FACTORES)
        + [config.COLUMNA_PUESTO, config.COLUMNA_CARGA]
    )
    return pd.DataFrame(filas, columns=columnas)


def plantilla_gripe_df() -> pd.DataFrame:
    """Plantilla del regresor externo opcional de gripe."""
    return pd.DataFrame(
        [
            {"anio": 2026, "mes": 1, "incidencia": 320.5},
            {"anio": 2026, "mes": 2, "incidencia": 280.0},
        ],
        columns=list(config.COLUMNAS_GRIPE),
    )


def a_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serializa un DataFrame a CSV (bytes) en el formato de plantilla."""
    return df.to_csv(index=False, sep=SEPARADOR).encode(CODIFICACION)


def plantilla_absentismo_csv() -> bytes:
    return a_csv_bytes(plantilla_absentismo_df())


def plantilla_gripe_csv() -> bytes:
    return a_csv_bytes(plantilla_gripe_df())
