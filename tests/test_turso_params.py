"""
tests/test_turso_params.py — Regresión: los parámetros de consulta deben ser
TUPLAS, no listas.

El cliente de Turso (libsql) exige tuplas y falla con listas
("'list' object cannot be converted to 'PyTuple'"). En local usamos sqlite3, que
acepta listas, así que el bug no se veía. Aquí envolvemos la conexión con una
que RECHAZA listas (como Turso) para cazarlo.
"""
from __future__ import annotations

import contextlib
import importlib
import sqlite3

import pandas as pd
import pytest


class _ConEstricta:
    """Envuelve una conexión sqlite3 real pero rechaza params tipo lista (como Turso)."""

    def __init__(self, real: sqlite3.Connection) -> None:
        self._r = real

    def execute(self, sql, params=None):
        if isinstance(params, list):
            raise TypeError(
                "Simulación Turso/libsql: 'list' object cannot be converted to 'PyTuple'"
            )
        return self._r.execute(sql) if params is None else self._r.execute(sql, params)

    def commit(self):
        self._r.commit()

    def close(self):
        self._r.close()


@pytest.fixture()
def persistencia_estricta(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    import config
    importlib.reload(config)
    from persistencia import db, factores, historico, previsiones
    for m in (db, historico, previsiones, factores):
        importlib.reload(m)
    db.inicializar_esquema(modo="real")

    @contextlib.contextmanager
    def conexion_estricta(modo="real"):
        con = sqlite3.connect(str(config.DB_PATH))
        try:
            yield _ConEstricta(con)
            con.commit()
        finally:
            con.close()

    for m in (historico, previsiones, factores):
        monkeypatch.setattr(m, "conexion", conexion_estricta)
    return historico, previsiones, factores


def test_lecturas_no_usan_listas_como_params(persistencia_estricta):
    historico, previsiones, factores = persistencia_estricta

    # Sanidad: el envoltorio realmente rechaza listas.
    with pytest.raises(TypeError):
        with historico.conexion("real") as con:
            con.execute("SELECT 1 WHERE 1 = ?", [1])

    # --- Histórico: guardar (tuplas) y leer con filtros (antes fallaba con lista) ---
    hist = pd.DataFrame([
        {"centro": "Albacete", "turno": "manana", "periodo": "2026-01",
         "tasa": 0.07, "jornadas_perdidas": 20, "plantilla": 25},
    ])
    historico.guardar_historico(hist, modo="real")
    leido = historico.leer_historico(centro="Albacete", turno="manana", modo="real")
    assert len(leido) == 1
    assert historico.listar_turnos(centro="Albacete", modo="real") == ["manana"]

    # --- Previsiones: guardar tanda y leer a fecha con centro/turno ---
    from datetime import datetime
    prev = pd.DataFrame([
        {"centro": "Albacete", "turno": "manana", "periodo_objetivo": "2026-02",
         "valor": 0.07, "lo": 0.05, "hi": 0.09, "modelo": "naive"},
    ])
    id_ej = previsiones.nueva_id_ejecucion()
    previsiones.guardar_tanda(prev, id_ej, fecha_calculo=datetime(2026, 1, 15), modo="real")
    assert len(previsiones.leer_tanda(id_ej, modo="real")) == 1
    a_fecha = previsiones.leer_prevision_a_fecha(
        datetime(2026, 2, 1), centro="Albacete", turno="manana", modo="real"
    )
    assert len(a_fecha) == 1

    # --- Factores: guardar y leer con filtros ---
    fac = pd.DataFrame([
        {"centro": "Albacete", "turno": "manana", "periodo": "2026-01",
         "tipo_horario": "fijo", "rotacion_pct": 15, "antiguedad_media": 8,
         "satisfaccion_media": 7, "jornada_media": 160},
    ])
    factores.guardar_factores(fac, modo="real")
    assert len(factores.leer_factores(centro="Albacete", modo="real")) == 1
