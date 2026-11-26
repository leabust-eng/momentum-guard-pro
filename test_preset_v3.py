"""El preset v3.0 debe copiar los inputs del Pine nuevo y usar riesgo en ATR."""

import numpy as np
import pandas as pd

from engine import Params, _State, _enter
from presets import PRESETS, ui_values

v3 = ui_values("TradingView v3.0")
assert v3 is not None, "falta el preset v3.0"

# CUSUM clásico (cambio real por vela) con los defaults del Pine v3.0.
assert v3["cusum_mode"] == "Clásico (impulso, v3.0)"
assert v3["cusum_vol_period"] == 20
assert v3["cusum_drift"] == 0.25
assert v3["cusum_threshold"] == 3.0
assert v3["pending_bars"] == 3

# Confirmación de mercado igual que v2.1 salvo la banda 1,6–2,8.
assert v3["ema_len"] == 200
assert v3["ema_slope_bars"] == 2
assert v3["require_2bars"] is True
assert v3["dist_mode"] == "ATR adaptativo"
assert v3["dist_atr_len"] == 14
assert v3["min_ema_dist_atr"] == 1.6
assert v3["max_ema_dist_atr"] == 2.8
assert v3["rsi_ob"] == 75.0 and v3["rsi_os"] == 30.0
assert v3["chop_len"] == 14 and v3["chop_max"] == 45.0
assert v3["zlag_len"] == 70 and v3["zlag_mult"] == 1.2

# Protección de capital en ATR: 4,5×ATR de stop y trailing desde 2,5×ATR.
assert v3["risk_mode"] == "ATR adaptativo"
assert v3["sl_atr_mult"] == 4.5
assert v3["ts_act_atr"] == 2.5
assert v3["ts_atr_len"] == 14
assert v3["ts_atr_mult"] == 6.0

# Dinero del Pine: 10.000 USDT, 1×, 100 %, 0,04 %, sin slippage ni funding.
assert v3["initial_capital"] == 10_000.0
assert v3["leverage"] == 1.0
assert v3["position_pct"] == 100
assert v3["commission_pct"] == 0.04
assert v3["slippage_pct"] == 0.0
assert v3["apply_funding"] is False
assert v3["exec_mode"] == "Cierre de vela (TV)"

# v2.1 sigue con la lógica vieja para que sus números publicados no cambien.
v21 = ui_values("TradingView v2.1")
assert v21["cusum_mode"] == "Persistencia (v2.1)"
assert v21["risk_mode"] == "Porcentaje fijo"

# Los presets por símbolo siguen en Persistencia + porcentaje fijo.
op = ui_values("OP/USDT:USDT")
assert op["cusum_mode"] == "Persistencia (v2.1)"
assert op["risk_mode"] == "Porcentaje fijo"

# El stop del modo ATR usa la distancia en ATR y no el porcentaje nominal.
df = pd.DataFrame(
    {
        "Open": [100.0] * 5,
        "High": [101.0] * 5,
        "Low": [99.0] * 5,
        "Close": [100.0] * 5,
        "Volume": [1.0] * 5,
    },
    index=pd.date_range("2026-01-01", periods=5, freq="15min", tz="UTC"),
)
atr_params = Params(risk_mode="ATR", sl_atr_mult=4.5, slippage=0.0, leverage=1.0)
st = _State(atr_params)
_enter(st, 1, 2, 100.0, df, atr_params, atr_entry=2.0)
assert np.isclose(st.stop_level, 100.0 - 4.5 * 2.0), st.stop_level

st = _State(atr_params)
_enter(st, -1, 2, 100.0, df, atr_params, atr_entry=2.0)
assert np.isclose(st.stop_level, 100.0 + 4.5 * 2.0), st.stop_level

pct_params = Params(risk_mode="Pct", sl_pct=0.04, slippage=0.0, leverage=1.0)
st = _State(pct_params)
_enter(st, 1, 2, 100.0, df, pct_params, atr_entry=2.0)
assert np.isclose(st.stop_level, 96.0), st.stop_level
# En modo porcentual el ATR de la entrada no debe alterar el stop.
assert not np.isnan(st.entry_atr)  # se guarda, pero no se usa

print("OK preset v3.0 ·", len(PRESETS), "presets · stop ATR 4,5× y % fijo")
