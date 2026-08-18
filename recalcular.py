"""
recalcular.py — Recálculo de previsiones, invocable FUERA de la interfaz.

El recálculo NO ocurre cuando un usuario abre la app: ocurre al pulsar el botón
"Recalcular previsión" en la interfaz o al ejecutar este CLI. Cada ejecución crea
una NUEVA `id_ejecucion` y AÑADE una tanda a la tabla `previsiones` (append-only).

Está pensado para poder programarse como job en el futuro (cron, tarea de Render,
etc.) sin depender de Streamlit.

Uso:
    python recalcular.py --modo prueba --sembrar-demo
    python recalcular.py --modo real --motor prophet --horizonte 6
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from config import PARAMS_MODELO
from modelo.prevision import calcular_prevision
from persistencia import db, historico, previsiones


@dataclass
class ResultadoRecalculo:
    id_ejecucion: str | None
    n_previsiones: int
    n_series: int
    modo: str
    motor: str
    avisos: list[str] = field(default_factory=list)
    mensaje: str = ""


def sembrar_demo_si_hace_falta(forzar: bool = False) -> int:
    """Carga el histórico demo en la base del modo prueba si está vacía (o si forzar)."""
    from datos_demo.generador import generar_historico_para_db

    db.inicializar_esquema(modo="prueba")
    existentes = historico.leer_historico(modo="prueba")
    if not existentes.empty and not forzar:
        return 0
    if forzar:
        historico.vaciar_historico(modo="prueba")
    hist = generar_historico_para_db()
    return historico.guardar_historico(hist, modo="prueba")


def recalcular(
    modo: str = "real",
    motor: str = PARAMS_MODELO.motor_por_defecto,
    horizonte: int = max(PARAMS_MODELO.horizontes_meses),
    sembrar_demo: bool = False,
    gripe_df: pd.DataFrame | None = None,
) -> ResultadoRecalculo:
    """Recalcula la previsión y AÑADE una tanda nueva a `previsiones`.

    En modo prueba puede sembrar el histórico sintético automáticamente.
    Devuelve un resumen con la id_ejecucion creada.
    """
    db.inicializar_esquema(modo=modo)

    if modo == "prueba":
        sembrar_demo_si_hace_falta(forzar=sembrar_demo)
        if gripe_df is None:
            from datos_demo.generador import generar_gripe
            gripe_df = generar_gripe()

    hist = historico.leer_historico(modo=modo)
    if hist.empty:
        return ResultadoRecalculo(
            id_ejecucion=None, n_previsiones=0, n_series=0, modo=modo, motor=motor,
            mensaje="No hay histórico cargado: nada que recalcular.",
        )

    # Tratamiento de bajas largas (config): reconstruimos las jornadas teóricas
    # (la tabla histórico no las guarda) como perdidas/tasa para poder topar/marcar.
    hist, n_bajas = _aplicar_bajas_largas(hist)

    resultado = calcular_prevision(hist, motor=motor, horizonte=horizonte, gripe_df=gripe_df)
    prev = resultado.previsiones
    if prev.empty:
        return ResultadoRecalculo(
            id_ejecucion=None, n_previsiones=0, n_series=0, modo=modo, motor=motor,
            avisos=resultado.avisos, mensaje="No se generó ninguna previsión.",
        )

    id_ej = previsiones.nueva_id_ejecucion()
    n = previsiones.guardar_tanda(prev, id_ej, fecha_calculo=datetime.now(), modo=modo)

    avisos = list(resultado.avisos)
    if n_bajas:
        from config import DEFINICION_ABSENTISMO
        trat = DEFINICION_ABSENTISMO.tratamiento_bajas_largas
        avisos.insert(0, f"Bajas largas ('{trat}'): {n_bajas} meses afectados.")
    return ResultadoRecalculo(
        id_ejecucion=id_ej,
        n_previsiones=n,
        n_series=len(resultado.detalle),
        modo=modo,
        motor=motor,
        avisos=avisos,
        mensaje=f"Tanda {id_ej[:8]}… guardada con {n} previsiones ({len(resultado.detalle)} series).",
    )


def _aplicar_bajas_largas(hist: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Aplica el tratamiento de bajas largas al histórico y devuelve (hist, n_afectadas).

    El criterio es robusto y relativo por centro×turno (múltiplo de la mediana),
    así que basta con las columnas centro/turno/tasa del propio histórico.
    """
    from ingesta.bajas_largas import tratar_bajas_largas

    tratado, informe = tratar_bajas_largas(hist)
    salida = hist.copy()
    salida["tasa"] = tratado["tasa"].to_numpy()
    return salida, informe.n_afectadas


def _main() -> None:
    parser = argparse.ArgumentParser(description="Recalcular previsiones de absentismo.")
    parser.add_argument("--modo", choices=["real", "prueba"], default="real")
    parser.add_argument("--motor", choices=["prophet", "sarima", "naive"],
                        default=PARAMS_MODELO.motor_por_defecto)
    parser.add_argument("--horizonte", type=int, default=max(PARAMS_MODELO.horizontes_meses))
    parser.add_argument("--sembrar-demo", action="store_true",
                        help="(modo prueba) regenera el histórico sintético antes de recalcular")
    args = parser.parse_args()

    res = recalcular(
        modo=args.modo, motor=args.motor, horizonte=args.horizonte,
        sembrar_demo=args.sembrar_demo,
    )
    print(res.mensaje)
    if res.avisos:
        print("Avisos:")
        for a in res.avisos:
            print("  -", a)


if __name__ == "__main__":
    _main()
