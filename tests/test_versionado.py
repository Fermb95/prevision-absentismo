"""
tests/test_versionado.py — Garantiza que la tabla `previsiones` NUNCA se sobrescribe.

Es la prueba que blinda la sección 7: cada recálculo AÑADE una tanda nueva y las
tandas anteriores se conservan íntegras.
"""
from __future__ import annotations

import importlib
from datetime import datetime, timedelta

import pandas as pd
import pytest


@pytest.fixture()
def db_temporal(tmp_path, monkeypatch):
    """Apunta DATA_DIR a un directorio temporal y reinicializa el esquema."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)

    import config
    importlib.reload(config)
    from persistencia import db, previsiones
    importlib.reload(db)
    importlib.reload(previsiones)
    db.inicializar_esquema()
    return previsiones


def _tanda(valor: float) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "centro": "Valencia", "turno": "noche",
                "periodo_objetivo": "2026-09", "valor": valor,
                "lo": valor - 0.01, "hi": valor + 0.01, "modelo": "prophet",
            }
        ]
    )


def test_dos_tandas_no_se_sobrescriben(db_temporal):
    prev = db_temporal
    id1 = prev.nueva_id_ejecucion()
    id2 = prev.nueva_id_ejecucion()

    prev.guardar_tanda(_tanda(0.10), id1, fecha_calculo=datetime(2026, 8, 1, 9, 0, 0))
    prev.guardar_tanda(_tanda(0.20), id2, fecha_calculo=datetime(2026, 8, 15, 9, 0, 0))

    # Las dos tandas siguen existiendo, con sus valores originales.
    t1 = prev.leer_tanda(id1)
    t2 = prev.leer_tanda(id2)
    assert len(t1) == 1 and len(t2) == 1
    assert t1.iloc[0]["valor"] == pytest.approx(0.10)
    assert t2.iloc[0]["valor"] == pytest.approx(0.20)

    # Hay exactamente 2 ejecuciones registradas.
    assert len(prev.listar_ejecuciones()) == 2


def test_lectura_a_fecha_toma_la_tanda_vigente(db_temporal):
    prev = db_temporal
    id1 = prev.nueva_id_ejecucion()
    id2 = prev.nueva_id_ejecucion()
    prev.guardar_tanda(_tanda(0.10), id1, fecha_calculo=datetime(2026, 8, 1))
    prev.guardar_tanda(_tanda(0.20), id2, fecha_calculo=datetime(2026, 8, 15))

    # A fecha 10-ago solo existía la primera tanda.
    a_dia_10 = prev.leer_prevision_a_fecha(datetime(2026, 8, 10))
    assert a_dia_10.iloc[0]["valor"] == pytest.approx(0.10)

    # A fecha 20-ago ya manda la segunda.
    a_dia_20 = prev.leer_prevision_a_fecha(datetime(2026, 8, 20))
    assert a_dia_20.iloc[0]["valor"] == pytest.approx(0.20)

    # Antes de cualquier tanda: vacío, no error.
    antes = prev.leer_prevision_a_fecha(datetime(2026, 7, 1))
    assert antes.empty


def test_no_existe_api_de_borrado_ni_update(db_temporal):
    """Refuerzo de diseño: el módulo no debe exponer borrar/actualizar previsiones."""
    prev = db_temporal
    prohibidas = [n for n in dir(prev) if any(
        k in n.lower() for k in ("borrar", "delete", "update", "actualizar", "vaciar")
    )]
    assert prohibidas == [], f"No debe haber API destructiva en previsiones: {prohibidas}"
