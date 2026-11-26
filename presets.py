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

DINERO_APP = {
    "initial_capital": 3_000.0,
    "leverage": 3.0,
    "position_pct": 90,
    "commission_pct": 0.05,
    "slippage_pct": 0.02,
    "apply_funding": True,
    "funding_pct": 0.01,
    "maintenance_pct": 0.5,
    "exec_mode": "Cierre de vela (TV)",
}

# Inputs de dinero del Pine v2.1: 10.000 USDT, 100 % del equity sin apalancar,
# comisión 0,04 % por lado, sin slippage y sin funding.
DINERO_TV = {
    "initial_capital": 10_000.0,
    "leverage": 1.0,
    "position_pct": 100,
    "commission_pct": 0.04,
    "slippage_pct": 0.0,
    "apply_funding": False,
    "funding_pct": 0.01,
    "maintenance_pct": 0.5,
    "exec_mode": "Cierre de vela (TV)",
}

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
        "ret_actual": 90.98,
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
        "bloques": 3,
        "ret_actual": -38.02,
        "ret_total": 114.86,
        "ops": 16,
        "pf": 11.07,
    },
    "AXS/USDT:USDT": {
        "etiqueta": "AXS · optimizado",
        "params": {
            "cusum_threshold": 3.0,
            "cusum_drift": 0.7,
            "pending_bars": 2,
            "ema_band": [1.0, 1.6],
            "rsi_ob": 80.0,
            "rsi_os": 25.0,
            "chop_max": 40.0,
            "zlag_len": 70,
            "zlag_mult": 1.8,
            "sl_pct": 0.05,
            "ts_act_pct": 0.01,
            "ts_atr_mult": 4.0,
        },
        "bloques": 3,
        "ret_actual": -10.72,
        "ret_total": 46.33,
        "ops": 18,
        "pf": 2.27,
    },
    "TradingView v2.1": {
        "etiqueta": "TradingView v2.1 · paridad",
        "nota": (
            "Copia exacta de los inputs por defecto del Pine v2.1: CUSUM "
            "20 / 0,5 / 5 / 3 velas, EMA 200 con pendiente de 2 velas y "
            "confirmación de 2 velas, banda ATR 1,5–6,0, RSI 75 / 30, CHOP 45, "
            "ZLEMA 70 / 1,2, stop 4 % y trailing 2 % / 6×ATR. Dinero: 10.000 "
            "USDT, 1×, 100 % de margen, comisión 0,04 %, sin slippage y sin "
            "funding. Cargalo para comparar contra TradingView con las mismas "
            "reglas; no es una configuración optimizada."
        ),
        "ui": {
            "cusum_mode": "Persistencia (v2.1)",
            "cusum_vol_period": 20,
            "cusum_drift": 0.5,
            "cusum_threshold": 5.0,
            "pending_bars": 3,
            "ema_len": 200,
            "ema_slope_bars": 2,
            "require_2bars": True,
            "dist_mode": "ATR adaptativo",
            "dist_atr_len": 14,
            "min_ema_dist_atr": 1.5,
            "max_ema_dist_atr": 6.0,
            "min_ema_dist_pct": 1.0,
            "max_ema_dist_pct": 1.6,
            "rsi_len": 14,
            "rsi_ob": 75.0,
            "rsi_os": 30.0,
            "chop_len": 14,
            "chop_max": 45.0,
            "zlag_len": 70,
            "zlag_mult": 1.2,
            "risk_mode": "Porcentaje fijo",
            "sl_pct": 4.0,
            "ts_act_pct": 2.0,
            "sl_atr_mult": 4.5,
            "ts_act_atr": 2.5,
            "ts_atr_len": 14,
            "ts_atr_mult": 6.0,
            **DINERO_TV,
        },
    },
    "TradingView v3.0": {
        "etiqueta": "TradingView v3.0 · paridad",
        "nota": (
            "Copia de los inputs por defecto del Pine v3.0: CUSUM **clásico** "
            "(cambio real por vela) 20 / 0,25 / 3 / 3 velas, banda ATR 1,6–2,8, "
            "RSI 75 / 30, CHOP 45, ZLEMA 70 / 1,2, stop 4,5×ATR, trailing "
            "desde 2,5×ATR y 6×ATR. Dinero: 10.000 USDT, 1×, comisión 0,04 %, "
            "sin slippage ni funding. Usalo para comparar con el Pine v3.0."
        ),
        "ui": {
            "cusum_mode": "Clásico (impulso, v3.0)",
            "cusum_vol_period": 20,
            "cusum_drift": 0.25,
            "cusum_threshold": 3.0,
            "pending_bars": 3,
            "ema_len": 200,
            "ema_slope_bars": 2,
            "require_2bars": True,
            "dist_mode": "ATR adaptativo",
            "dist_atr_len": 14,
            "min_ema_dist_atr": 1.6,
            "max_ema_dist_atr": 2.8,
            "min_ema_dist_pct": 1.0,
            "max_ema_dist_pct": 1.7,
            "rsi_len": 14,
            "rsi_ob": 75.0,
            "rsi_os": 30.0,
            "chop_len": 14,
            "chop_max": 45.0,
            "zlag_len": 70,
            "zlag_mult": 1.2,
            "risk_mode": "ATR adaptativo",
            "sl_atr_mult": 4.5,
            "ts_act_atr": 2.5,
            "sl_pct": 4.0,
            "ts_act_pct": 2.0,
            "ts_atr_len": 14,
            "ts_atr_mult": 6.0,
            **DINERO_TV,
        },
    },
}


DEFAULT_UI = {
    "cusum_mode": "Persistencia (v2.1)",
    "cusum_vol_period": 30,
    "cusum_drift": 0.5,
    "cusum_threshold": 5.0,
    "pending_bars": 1,
    "ema_len": 200,
    "ema_slope_bars": 1,
    "require_2bars": False,
    "dist_mode": "ATR adaptativo",
    "dist_atr_len": 14,
    "min_ema_dist_atr": 1.5,
    "max_ema_dist_atr": 6.0,
    "min_ema_dist_pct": 1.0,
    "max_ema_dist_pct": 1.6,
    "rsi_len": 14,
    "rsi_ob": 75.0,
    "rsi_os": 20.0,
    "chop_len": 14,
    "chop_max": 50.0,
    "zlag_len": 70,
    "zlag_mult": 2.2,
    "risk_mode": "Porcentaje fijo",
    "sl_pct": 4.0,
    "ts_act_pct": 2.0,
    "sl_atr_mult": 4.5,
    "ts_act_atr": 2.5,
    "ts_atr_len": 14,
    "ts_atr_mult": 6.0,
    **DINERO_APP,
}


def ui_values(symbol: str) -> dict | None:
    """Devuelve los valores en las unidades que usan los widgets del sidebar."""
    if symbol == "Actual (por defecto)":
        return dict(DEFAULT_UI)
    preset = PRESETS.get(symbol)
    if preset is None:
        return None
    # Los presets de paridad traen los valores ya listos para la UI.
    if "ui" in preset:
        return dict(preset["ui"])
    p = preset["params"]
    lo, hi = p["ema_band"]
    return {
        # Siguen en la lógica v2.1 con la que se optimizaron.
        "cusum_mode": "Persistencia (v2.1)",
        "risk_mode": "Porcentaje fijo",
        "sl_atr_mult": 4.5,
        "ts_act_atr": 2.5,
        "cusum_drift": p["cusum_drift"],
        "cusum_threshold": p["cusum_threshold"],
        "pending_bars": p["pending_bars"],
        # Los presets se optimizaron midiendo la banda en %, así que la fuerzan.
        "dist_mode": "Porcentaje fijo",
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
        # Estos presets se validaron con el dinero por defecto de la app, así
        # que lo restauran (si antes cargaste el preset de paridad).
        **DINERO_APP,
    }
