"""
ingesta/fuente.py — Interfaz de fuentes de datos (patrón de puerto/adaptador).

`FuenteDatos` define el CONTRATO: cualquier origen debe saber entregar el panel
de absentismo bruto y (opcionalmente) la curva de gripe. Hoy solo hay una
implementación real, `FuenteCSV`. `FuenteAPI` queda como STUB documentado para
enchufar en el futuro SuccessFactors (OData) o el WMS SIN reescribir el resto de
la app: bastará implementar sus dos métodos de lectura.

Nota: las fuentes devuelven datos BRUTOS. La validación (incluida la barrera de
privacidad) y la normalización viven en `ingesta/validacion.py`, de modo que
toda entrada —venga de CSV o del futuro API— pasa por el mismo filtro.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import pandas as pd

from ingesta.validacion import (
    ResultadoValidacion,
    validar_absentismo,
    validar_gripe,
)


class FuenteDatos(ABC):
    """Contrato común a toda fuente de datos de entrada."""

    @property
    @abstractmethod
    def descripcion(self) -> str:
        """Texto legible de la fuente (para mostrar en la interfaz)."""

    @abstractmethod
    def leer_absentismo(self) -> pd.DataFrame:
        """Devuelve el panel de absentismo BRUTO (sin validar aún)."""

    @abstractmethod
    def leer_gripe(self) -> pd.DataFrame | None:
        """Devuelve la curva de gripe bruta, o None si la fuente no la aporta."""


# ---------------------------------------------------------------------------
# Implementación real: CSV / Excel subidos desde la interfaz
# ---------------------------------------------------------------------------
class FuenteCSV(FuenteDatos):
    """Lee de ficheros CSV o Excel (ruta en disco o buffer subido por Streamlit)."""

    def __init__(
        self,
        absentismo: Any,
        gripe: Any | None = None,
        nombre: str = "Ficheros subidos",
    ) -> None:
        self._absentismo = absentismo
        self._gripe = gripe
        self._nombre = nombre

    @property
    def descripcion(self) -> str:
        return f"CSV/Excel — {self._nombre}"

    def leer_absentismo(self) -> pd.DataFrame:
        return self._leer(self._absentismo)

    def leer_gripe(self) -> pd.DataFrame | None:
        if self._gripe is None:
            return None
        return self._leer(self._gripe)

    # -- utilidades internas --
    @staticmethod
    def _leer(fichero: Any) -> pd.DataFrame:
        """Lee CSV o Excel de una ruta o de un buffer (UploadedFile de Streamlit)."""
        nombre = FuenteCSV._nombre_fichero(fichero)
        if nombre.lower().endswith((".xlsx", ".xlsm", ".xls")):
            return pd.read_excel(fichero, engine="openpyxl")
        # CSV: autodetecta separador (',' o ';') con el motor de Python.
        # 'utf-8-sig' absorbe el BOM que añade Excel; si falla, probamos latin-1.
        for encoding in ("utf-8-sig", "latin-1"):
            if hasattr(fichero, "seek"):
                fichero.seek(0)
            try:
                return pd.read_csv(
                    fichero, sep=None, engine="python", decimal=".", encoding=encoding
                )
            except (UnicodeDecodeError, UnicodeError):
                continue
        # Último intento sin especificar codificación (deja decidir a pandas).
        if hasattr(fichero, "seek"):
            fichero.seek(0)
        return pd.read_csv(fichero, sep=None, engine="python", decimal=".")

    @staticmethod
    def _nombre_fichero(fichero: Any) -> str:
        if isinstance(fichero, (str, Path)):
            return str(fichero)
        # UploadedFile de Streamlit expone .name
        return getattr(fichero, "name", "")


# ---------------------------------------------------------------------------
# STUB documentado para el futuro (NO implementar ahora)
# ---------------------------------------------------------------------------
class FuenteAPI(FuenteDatos):
    """STUB: futura fuente vía API (SuccessFactors OData o WMS). NO implementada.

    Diseño previsto para no reescribir el resto de la app:
      * El constructor recibirá credenciales/endpoint (base_url, token, entidad).
      * `leer_absentismo()` consultará el endpoint OData y devolverá el panel YA
        agregado por centro/turno/mes (la API/consulta debe agregar en origen;
        esta app NUNCA recibe datos individuales).
      * `leer_gripe()` podrá tirar de una fuente epidemiológica pública.
      * La salida bruta pasará por `ingesta/validacion.py`, igual que el CSV, así
        que la barrera de privacidad se aplica también a este origen.

    Ejemplo de uso futuro (ilustrativo):
        fuente = FuenteAPI(base_url="https://api...", token="...", entidad="Absence")
        panel = cargar_y_validar(fuente)
    """

    def __init__(self, base_url: str, token: str, entidad: str = "Absence") -> None:
        self.base_url = base_url
        self.token = token
        self.entidad = entidad

    @property
    def descripcion(self) -> str:
        return f"API (stub) — {self.base_url}/{self.entidad}"

    def leer_absentismo(self) -> pd.DataFrame:
        raise NotImplementedError(
            "FuenteAPI aún no está implementada. Es un stub para conectar en el "
            "futuro SuccessFactors (OData) o el WMS. La consulta debe devolver los "
            "datos YA AGREGADOS por centro/turno/mes (nunca a nivel de persona)."
        )

    def leer_gripe(self) -> pd.DataFrame | None:
        raise NotImplementedError(
            "FuenteAPI.leer_gripe aún no está implementada (stub)."
        )


# ---------------------------------------------------------------------------
# Orquestación: leer de una fuente + validar (misma barrera para todo origen)
# ---------------------------------------------------------------------------
def cargar_y_validar(
    fuente: FuenteDatos,
) -> tuple[ResultadoValidacion, ResultadoValidacion | None]:
    """Lee de la fuente y valida absentismo (y gripe si la aporta).

    Devuelve (resultado_absentismo, resultado_gripe|None). No persiste nada:
    la interfaz muestra la vista previa y decide si confirmar la carga.
    """
    res_abs = validar_absentismo(fuente.leer_absentismo())

    res_gripe: ResultadoValidacion | None = None
    df_gripe = fuente.leer_gripe()
    if df_gripe is not None:
        res_gripe = validar_gripe(df_gripe)

    return res_abs, res_gripe
