"""
config.py — Configuración central de la app de previsión de absentismo.

Aquí viven las reglas NO NEGOCIABLES (privacidad, definición de absentismo)
y todos los parámetros/umbrales, para no tenerlos dispersos por el código.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. RUTAS Y PERSISTENCIA
# ---------------------------------------------------------------------------
# DATA_DIR se lee SIEMPRE de entorno. En Render debe apuntar al disco
# persistente (p. ej. /data); en local, por defecto ./datos.
# Sin esto, cada redespliegue en Render borraría el histórico de previsiones.
DATA_DIR: Path = Path(os.environ.get("DATA_DIR", "./datos")).resolve()
DB_PATH: Path = DATA_DIR / "absentismo.sqlite"
# El modo prueba usa SIEMPRE una base local desechable (nunca Turso): sus datos
# son sintéticos y regenerables, así no contaminan el histórico real.
DB_PATH_DEMO: Path = DATA_DIR / "absentismo_demo.sqlite"

# Persistencia en la nube (opcional, gratis) — Turso / libSQL.
# Si estas dos variables están definidas, la app usa Turso (SQLite en la nube,
# persistente) en lugar del fichero local. Si no, usa el fichero DATA_DIR.
# Esto permite desplegar GRATIS en hosts de disco efímero (Render free) sin
# perder el histórico de previsiones versionadas (ver README, sección 7).
TURSO_DATABASE_URL: str | None = os.environ.get("TURSO_DATABASE_URL") or None
TURSO_AUTH_TOKEN: str | None = os.environ.get("TURSO_AUTH_TOKEN") or None


def usa_turso() -> bool:
    """Devuelve True si la app debe conectarse a Turso en lugar de a SQLite local."""
    return bool(TURSO_DATABASE_URL)


# ---------------------------------------------------------------------------
# 2. PRIVACIDAD — REGLAS INNEGOCIABLES
# ---------------------------------------------------------------------------
# Si un fichero subido contiene CUALQUIERA de estas columnas (o algo que
# empiece/contenga estos términos), la carga se RECHAZA. La app solo admite
# datos agregados por centro/turno/mes; nunca datos de personas ni de salud.
COLUMNAS_PERSONALES_PROHIBIDAS: tuple[str, ...] = (
    "nombre", "apellido", "apellidos", "dni", "nif", "nie", "id_empleado",
    "empleado", "trabajador", "email", "correo", "telefono", "movil",
    "edad", "fecha_nacimiento", "nacimiento", "sexo", "genero", "género",
    "diagnostico", "diagnóstico", "enfermedad", "patologia", "patología",
    "matricula", "seg_social", "seguridad_social", "num_afiliacion",
)

# El MODELO nunca puede usar estas variables como predictoras, ni aunque
# alguien las colara. Se comprueba en el modelo antes de ajustar.
PREDICTORES_PROHIBIDOS: tuple[str, ...] = (
    "edad", "sexo", "genero", "género", "fecha_nacimiento",
)

# Predictores PERMITIDOS (documentados aquí como fuente de verdad):
# calendario/estacionalidad, carga de trabajo, tendencia del propio centro,
# y (opcional) curva de gripe como regresor externo.
PREDICTORES_PERMITIDOS: tuple[str, ...] = (
    "estacionalidad", "tendencia", "carga_trabajo", "gripe",
)

# ---------------------------------------------------------------------------
# 3. ESQUEMA DE DATOS DE ENTRADA
# ---------------------------------------------------------------------------
TURNOS_VALIDOS: tuple[str, ...] = ("manana", "tarde", "noche", "todos")

COLUMNAS_ABSENTISMO: tuple[str, ...] = (
    "centro", "turno", "anio", "mes",
    "plantilla_media", "jornadas_teoricas", "jornadas_perdidas",
)
# Columna alternativa: si viene 'tasa' directa, se admite en lugar de calcularla.
COLUMNA_TASA_ALTERNATIVA: str = "tasa"

COLUMNAS_GRIPE: tuple[str, ...] = ("anio", "mes", "incidencia")

# Factores estructurales OPCIONALES por centro/turno (agregados, nunca de persona).
# Si vienen en el fichero de absentismo, se guardan y se usan para el análisis de
# drivers (qué característica del CENTRO se asocia con más/menos absentismo).
COLUMNAS_FACTORES: tuple[str, ...] = (
    "tipo_horario",        # 'flexible' | 'fijo' | 'rotativo'
    "rotacion_pct",        # rotación anual de plantilla del centro (%)
    "antiguedad_media",    # antigüedad media de la plantilla (años)
    "satisfaccion_media",  # satisfacción media (encuesta anónima, p. ej. 1–10)
    "jornada_media",       # jornada media mensual (horas)
)
TIPOS_HORARIO: tuple[str, ...] = ("flexible", "fijo", "rotativo")
# Factores numéricos y su rango razonable (para validación con avisos).
RANGOS_FACTORES: dict[str, tuple[float, float]] = {
    "rotacion_pct": (0.0, 100.0),
    "antiguedad_media": (0.0, 50.0),
    "satisfaccion_media": (0.0, 10.0),
    "jornada_media": (0.0, 320.0),
}

# ---------------------------------------------------------------------------
# 4. DEFINICIÓN DE ABSENTISMO Y TRATAMIENTO DE BAJAS LARGAS
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DefinicionAbsentismo:
    """Qué se cuenta como absentismo y cómo tratar las bajas largas.

    Las bajas largas (IT prolongada) distorsionan la serie: son eventos
    puntuales de muy alto impacto que no representan la dinámica habitual.
    Por eso se permite TOPAR (cap) o MARCAR (flag) las ausencias muy largas.
    Esta decisión está documentada en el README.
    """
    # 'incluir': se cuentan tal cual (serie cruda).
    # 'topar':   se winsoriza el mes atípico al umbral (suaviza picos extremos).
    # 'marcar':  se dejan pero se señalan como outlier para el modelo/aviso.
    tratamiento_bajas_largas: str = "topar"

    # Con datos AGREGADOS no podemos aislar una baja individual larga; solo vemos
    # el total mensual. Por eso un mes se considera "baja larga" (atípico) cuando
    # su tasa supera `factor_baja_larga` veces la MEDIANA del propio centro×turno.
    # Es robusto y relativo a cada centro; la estacionalidad normal (pico de
    # invierno ~1,3× la mediana) no se toca, solo los picos genuinamente extremos.
    factor_baja_larga: float = 2.5

    # Qué conceptos se consideran absentismo (documental; los datos ya llegan
    # agregados como jornadas perdidas, esto guía la interpretación/README).
    conceptos_incluidos: tuple[str, ...] = (
        "it_comun", "it_no_laboral", "ausencia_injustificada", "permiso_no_retribuido",
    )
    conceptos_excluidos: tuple[str, ...] = (
        "vacaciones", "permiso_retribuido", "formacion", "maternidad_paternidad",
    )


DEFINICION_ABSENTISMO = DefinicionAbsentismo()

# ---------------------------------------------------------------------------
# 5. MODELO Y PREVISIÓN
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ParametrosModelo:
    motor_por_defecto: str = "prophet"          # "prophet" | "sarima"
    intervalo_confianza: float = 0.90           # banda 90% (lo, hi)
    horizontes_meses: tuple[int, ...] = (3, 6)  # previsión a 3 y 6 meses
    # Nº mínimo de meses de histórico para no avisar de baja fiabilidad.
    min_meses_fiable: int = 12
    # Por debajo de esto se puede ajustar pero se marca "baja fiabilidad".
    min_meses_para_ajustar: int = 6


PARAMS_MODELO = ParametrosModelo()

# ---------------------------------------------------------------------------
# 6. MÉTRICAS Y ALERTAS DE DERIVA
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class UmbralesSemaforo:
    """Cortes para el color de KPIs y del panel resumen (en tasa, fracción 0–1)."""
    verde_max: float = 0.06   # < 6% → verde
    ambar_max: float = 0.10   # 6–10% → ámbar; > 10% → rojo


UMBRALES_SEMAFORO = UmbralesSemaforo()


@dataclass(frozen=True)
class UmbralesAlerta:
    # Deriva: nº de meses consecutivos por encima del umbral de error que
    # disparan la alerta en la página de Precisión.
    meses_consecutivos_deriva: int = 3
    # Umbral de MAPE (en %) por encima del cual un mes cuenta como "desviado".
    mape_umbral_deriva: float = 20.0


UMBRALES_ALERTA = UmbralesAlerta()

# ---------------------------------------------------------------------------
# 7. DATOS DEMO (MODO PRUEBA)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ParametrosDemo:
    centros: tuple[str, ...] = (
        "Valencia", "Sevilla", "Bilbao", "Zaragoza", "Málaga", "Valladolid",
    )
    meses_historico: int = 18
    semilla_base: int = 1995  # +offset por centro → reproducible por centro


PARAMS_DEMO = ParametrosDemo()

# ---------------------------------------------------------------------------
# 8. INTERFAZ / DESPLIEGUE
# ---------------------------------------------------------------------------
MODO_POR_DEFECTO: str = "prueba"   # la app abre SIEMPRE en modo prueba
IDIOMA: str = "es"
LOCALE_NUMEROS: str = "es_ES"      # separador de miles '.', decimal ','

# Protección opcional por contraseña (sin sistema de usuarios).
# Si APP_PASSWORD no está definida, la app queda abierta.
APP_PASSWORD: str | None = os.environ.get("APP_PASSWORD") or None
