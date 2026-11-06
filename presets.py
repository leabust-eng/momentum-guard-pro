"""Presets de estrategia validados con walk-forward.

Cada preset fue encontrado con `optimize_symbols.py` (búsqueda aleatoria sobre el
70 % inicial de los datos) y después validado en `validate_presets.py` partiendo
el histórico en 3 bloques temporales.

`bloques` indica en cuántos de esos 3 bloques el preset terminó en positivo con
al menos 2 operaciones. Un preset con 3/3 es el que menos depende de un tramo
puntual; aun así, el histórico disponible (15m desde 2026-07-28) es corto y esto
NO es una garantía de rentabilidad futura.

Los retornos están calculados con los valores por defecto de la app: 3.000 USDT,
leverage 3× y 90 % de margen por operación.

AAVE y ETH no tienen preset a propósito: con la configuración actual ya ganan en
los 3 bloques (AAVE +346 % con el preset, +450 % con la actual; ETH +140 %), así
que no hay nada que optimizar ahí.
"""

PRESETS: dict[str, dict] = {
    "OP/USDT:USDT": {
        "etiqueta": "OP · optimizado",
        "params": {
            "cusum_threshold": 7.0,
            "cusum_drift": 0.7,
            "pending_bars": 2,
            "ema_band": [0.5, 1.5],
            "rsi_ob": 75.0,
            "rsi_os": 30.0,
            "chop_max": 55.0,
            "zlag_len": 70,
            "zlag_mult": 2.2,
            "sl_pct": 0.05,
            "ts_act_pct": 0.01,
            "ts_atr_mult": 4.0,
        },
        "bloques": 3,
        "ret_actual": 107.45,
        "ret_total": 142.52,
        "ops": 26,
        "pf": 3.16,
    },
    "AVAX/USDT:USDT": {
        "etiqueta": "AVAX · optimizado",
        "params": {
            "cusum_threshold": 6.0,
            "cusum_drift": 0.3,
            "pending_bars": 1,
            "ema_band": [1.5, 2.5],
            "rsi_ob": 80.0,
            "rsi_os": 30.0,
            "chop_max": 50.0,
            "zlag_len": 50,
            "zlag_mult": 2.2,
            "sl_pct": 0.02,
            "ts_act_pct": 0.01,
            "ts_atr_mult": 6.0,
        },
        "bloques": 3,
        "ret_actual": -31.73,
        "ret_total": 178.28,
        "ops": 29,
        "pf": 3.14,
    },
    "LINK/USDT:USDT": {
        "etiqueta": "LINK · optimizado",
        "params": {
            "cusum_threshold": 3.0,
            "cusum_drift": 0.7,
            "pending_bars": 1,
            "ema_band": [1.0, 2.0],
            "rsi_ob": 70.0,
            "rsi_os": 30.0,
            "chop_max": 45.0,
            "zlag_len": 50,
            "zlag_mult": 2.2,
            "sl_pct": 0.02,
            "ts_act_pct": 0.02,
            "ts_atr_mult": 4.0,
        },
        "bloques": 3,
        "ret_actual": 29.03,
        "ret_total": 114.17,
        "ops": 18,
        "pf": 4.42,
    },
    "BTC/USDT:USDT": {
        "etiqueta": "BTC · optimizado (frágil)",
        "params": {
            "cusum_threshold": 7.0,
            "cusum_drift": 0.3,
            "pending_bars": 2,
            "ema_band": [0.5, 1.5],
            "rsi_ob": 75.0,
            "rsi_os": 25.0,
            "chop_max": 45.0,
            "zlag_len": 50,
            "zlag_mult": 2.6,
            "sl_pct": 0.06,
            "ts_act_pct": 0.01,
            "ts_atr_mult": 8.0,
        },
        "bloques": 2,
        "ret_actual": -38.02,
        "ret_total": 114.86,
        "ops": 16,
        "pf": 11.07,
    },
}


DEFAULT_UI = {
    "cusum_drift": 0.5,
    "cusum_threshold": 5.0,
    "pending_bars": 1,
    "min_ema_dist_pct": 1.0,
    "max_ema_dist_pct": 1.6,
    "rsi_ob": 75.0,
    "rsi_os": 20.0,
    "chop_max": 50.0,
    "zlag_len": 70,
    "zlag_mult": 2.2,
    "sl_pct": 4.0,
    "ts_act_pct": 2.0,
    "ts_atr_mult": 6.0,
}


def ui_values(symbol: str) -> dict | None:
    """Devuelve los valores en las unidades que usan los widgets del sidebar."""
    if symbol == "Actual (por defecto)":
        return dict(DEFAULT_UI)
    preset = PRESETS.get(symbol)
    if preset is None:
        return None
    p = preset["params"]
    lo, hi = p["ema_band"]
    return {
        "cusum_drift": p["cusum_drift"],
        "cusum_threshold": p["cusum_threshold"],
        "pending_bars": p["pending_bars"],
        "min_ema_dist_pct": lo,
        "max_ema_dist_pct": hi,
        "rsi_ob": p["rsi_ob"],
        "rsi_os": p["rsi_os"],
        "chop_max": p["chop_max"],
        "zlag_len": p["zlag_len"],
        "zlag_mult": p["zlag_mult"],
        "sl_pct": p["sl_pct"] * 100.0,
        "ts_act_pct": p["ts_act_pct"] * 100.0,
        "ts_atr_mult": p["ts_atr_mult"],
    }
