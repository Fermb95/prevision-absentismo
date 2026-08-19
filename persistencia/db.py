"""
persistencia/db.py — Conexión y esquema de la base de datos.

Abstrae DÓNDE se guardan los datos:
  * En local (o cualquier host con disco): fichero SQLite en DATA_DIR (stdlib sqlite3).
  * En producción gratuita (Render free): Turso / libSQL (SQLite en la nube),
    si están definidas TURSO_DATABASE_URL y TURSO_AUTH_TOKEN.

El resto de la app (historico.py, previsiones.py) no necesita saber cuál se usa:
llama a `conexion()` y trabaja con una conexión DB-API estándar (placeholders '?').
"""
from __future__ import annotations

import contextlib
from typing import Any, Iterator

import config


# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------
def _conectar(modo: str = "real") -> Any:
    """Abre una conexión al backend según el modo.

    modo="real": Turso si está configurado; si no, SQLite local (DB_PATH).
    modo="prueba": SIEMPRE SQLite local desechable (DB_PATH_DEMO), nunca Turso.
    """
    if modo == "real" and config.usa_turso():
        return _conectar_turso()

    # SQLite local. Aseguramos que DATA_DIR existe.
    import sqlite3

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    ruta = config.DB_PATH_DEMO if modo == "prueba" else config.DB_PATH
    con = sqlite3.connect(str(ruta))
    con.execute("PRAGMA journal_mode=WAL;")  # mejor concurrencia lectura/escritura
    return con


def _conectar_turso() -> Any:
    """Conexión remota a Turso (SQLite en la nube). Aislada y con error accionable.

    Usa `libsql-experimental` (import perezoso: solo se necesita en producción).
    Las escrituras van directas a la nube, así el histórico persiste aunque el
    disco del host sea efímero. Si algo falla, se lanza un error claro.
    """
    try:
        import libsql_experimental as libsql  # type: ignore
    except Exception as exc:  # paquete no instalado o sin wheel para esta versión
        raise RuntimeError(
            "No se pudo importar 'libsql-experimental' (necesario para Turso). "
            "En Render/Python 3.11 se instala vía requirements.txt. "
            f"Detalle: {exc}"
        ) from exc
    try:
        return libsql.connect(
            database=config.TURSO_DATABASE_URL,
            auth_token=config.TURSO_AUTH_TOKEN,
        )
    except Exception as exc:
        raise RuntimeError(
            "No se pudo conectar a Turso. Revisa TURSO_DATABASE_URL (debe empezar "
            "por 'libsql://') y TURSO_AUTH_TOKEN en las variables de entorno. "
            f"Detalle: {exc}"
        ) from exc


def probar_conexion(modo: str) -> tuple[bool, str]:
    """Comprueba que el backend responde (para el botón 'Probar conexión')."""
    try:
        with conexion(modo) as con:
            con.execute("SELECT 1")
        return True, f"Conexión correcta con: {describe_backend(modo)}"
    except Exception as exc:
        return False, f"Fallo de conexión: {exc}"


@contextlib.contextmanager
def conexion(modo: str = "real") -> Iterator[Any]:
    """Context manager: entrega una conexión y hace commit/close al salir."""
    con = _conectar(modo)
    try:
        yield con
        con.commit()
    finally:
        with contextlib.suppress(Exception):
            con.close()


def describe_backend(modo: str = "real") -> str:
    """Texto legible del backend en uso (para mostrar en la interfaz)."""
    if modo == "prueba":
        return f"SQLite local desechable — modo prueba ({config.DB_PATH_DEMO})"
    if config.usa_turso():
        return "Turso (SQLite en la nube, persistente)"
    return f"SQLite local ({config.DB_PATH})"


# ---------------------------------------------------------------------------
# Esquema
# ---------------------------------------------------------------------------
_ESQUEMA: tuple[str, ...] = (
    # Histórico observado (agregado por centro/turno/mes). Se puede actualizar
    # (upsert) cuando se recargan datos: la clave es (centro, turno, periodo).
    """
    CREATE TABLE IF NOT EXISTS historico (
        centro           TEXT    NOT NULL,
        turno            TEXT    NOT NULL,
        periodo          TEXT    NOT NULL,   -- 'YYYY-MM'
        tasa             REAL    NOT NULL,   -- jornadas_perdidas / jornadas_teoricas
        jornadas_perdidas INTEGER,
        plantilla        INTEGER,
        PRIMARY KEY (centro, turno, periodo)
    )
    """,
    # Previsiones VERSIONADAS. Tabla APPEND-ONLY: cada recálculo añade una tanda
    # nueva con su fecha_calculo. NUNCA se hace UPDATE ni DELETE aquí.
    """
    CREATE TABLE IF NOT EXISTS previsiones (
        id_ejecucion    TEXT    NOT NULL,   -- identifica la tanda (una por recálculo)
        fecha_calculo   TEXT    NOT NULL,   -- ISO 'YYYY-MM-DD HH:MM:SS'
        centro          TEXT    NOT NULL,
        turno           TEXT    NOT NULL,
        periodo_objetivo TEXT   NOT NULL,   -- 'YYYY-MM' del mes previsto
        valor           REAL    NOT NULL,   -- tasa central prevista
        lo              REAL    NOT NULL,   -- límite inferior del intervalo 90%
        hi              REAL    NOT NULL,   -- límite superior del intervalo 90%
        modelo          TEXT    NOT NULL    -- 'prophet' | 'sarima'
    )
    """,
    # Factores estructurales por centro/turno (agregados, opcionales). Se pueden
    # actualizar (upsert) igual que el histórico.
    """
    CREATE TABLE IF NOT EXISTS factores (
        centro            TEXT NOT NULL,
        turno             TEXT NOT NULL,
        periodo           TEXT NOT NULL,   -- 'YYYY-MM'
        tipo_horario      TEXT,            -- 'flexible' | 'fijo' | 'rotativo'
        rotacion_pct      REAL,
        antiguedad_media  REAL,
        satisfaccion_media REAL,
        jornada_media     REAL,
        PRIMARY KEY (centro, turno, periodo)
    )
    """,
    # Índices para las consultas típicas.
    "CREATE INDEX IF NOT EXISTS idx_hist_centro_turno ON historico (centro, turno)",
    "CREATE INDEX IF NOT EXISTS idx_prev_fecha ON previsiones (fecha_calculo)",
    "CREATE INDEX IF NOT EXISTS idx_prev_centro_turno ON previsiones (centro, turno)",
)


def inicializar_esquema(modo: str = "real") -> None:
    """Crea las tablas e índices si no existen. Idempotente."""
    with conexion(modo) as con:
        for sentencia in _ESQUEMA:
            con.execute(sentencia)


# ---------------------------------------------------------------------------
# Utilidad: convertir resultado de cursor a lista de dicts (portable entre
# sqlite3 y libsql, sin depender de pandas.read_sql).
# ---------------------------------------------------------------------------
def filas_como_dicts(cursor: Any) -> list[dict[str, Any]]:
    """Convierte las filas de un cursor ya ejecutado en lista de dicts."""
    columnas = [desc[0] for desc in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
