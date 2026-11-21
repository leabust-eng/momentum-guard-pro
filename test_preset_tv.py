"""El preset de paridad debe reproducir los inputs por defecto del Pine v2.1."""

from presets import DEFAULT_UI, PRESETS, ui_values

tv = ui_values("TradingView v2.1")
assert tv is not None, "falta el preset de paridad"

# Estrategia (Pine v2.1 → defaults)
assert tv["cusum_vol_period"] == 20
assert tv["cusum_drift"] == 0.5
assert tv["cusum_threshold"] == 5.0
assert tv["pending_bars"] == 3
assert tv["ema_len"] == 200
assert tv["ema_slope_bars"] == 2
assert tv["require_2bars"] is True
assert tv["dist_mode"] == "ATR adaptativo"
assert tv["dist_atr_len"] == 14
assert tv["min_ema_dist_atr"] == 1.5
assert tv["max_ema_dist_atr"] == 6.0
assert tv["rsi_len"] == 14
assert tv["rsi_ob"] == 75.0
assert tv["rsi_os"] == 30.0
assert tv["chop_len"] == 14
assert tv["chop_max"] == 45.0
assert tv["zlag_len"] == 70
assert tv["zlag_mult"] == 1.2
assert tv["sl_pct"] == 4.0
assert tv["ts_act_pct"] == 2.0
assert tv["ts_atr_len"] == 14
assert tv["ts_atr_mult"] == 6.0

# Dinero (Pine: 10.000 USDT, sin leverage, 0,04 %, sin funding ni slippage)
assert tv["initial_capital"] == 10_000.0
assert tv["leverage"] == 1.0
assert tv["position_pct"] == 100
assert tv["commission_pct"] == 0.04
assert tv["slippage_pct"] == 0.0
assert tv["apply_funding"] is False
assert tv["exec_mode"] == "Cierre de vela (TV)"

# "Actual" vuelve a los defaults de la app.
actual = ui_values("Actual (por defecto)")
assert actual["initial_capital"] == 3_000.0
assert actual["leverage"] == 3.0
assert actual["position_pct"] == 90
assert actual["pending_bars"] == 1
assert actual["zlag_mult"] == 2.2
assert actual["rsi_os"] == 20.0
assert DEFAULT_UI["chop_max"] == 50.0

# Los presets por símbolo siguen en % y restauran el dinero de la app (así sus
# retornos documentados siguen siendo válidos aunque antes cargues paridad).
op = ui_values("OP/USDT:USDT")
assert op["dist_mode"] == "Porcentaje fijo"
assert op["initial_capital"] == 3_000.0 and op["leverage"] == 3.0

assert ui_values("NOPE/USDT:USDT") is None
print("OK preset TradingView v2.1 ·", len(PRESETS), "presets")
