"""Regresión de la Banda Elástica: modo ATR adaptativo vs porcentaje fijo."""

import pandas as pd

from engine import Params, _ema_band_mask
from presets import ui_values

idx = pd.date_range("2026-01-01", periods=60, freq="15min")


def marco(high: float, low: float, close: float) -> tuple[pd.DataFrame, pd.Series]:
    df = pd.DataFrame(
        {
            "Open": close,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": 1.0,
        },
        index=idx,
    )
    ema = pd.Series(100.0, index=idx)
    return df, ema


pct = Params(
    use_ema_dist=True,
    dist_mode="Pct",
    min_ema_dist_pct=1.0,
    max_ema_dist_pct=4.0,
)
atr = Params(
    use_ema_dist=True,
    dist_mode="ATR",
    dist_atr_len=14,
    min_ema_dist_atr=1.5,
    max_ema_dist_atr=6.0,
)

# ATR chico (0.10): 2 % de distancia son 20 ATR -> fuera de la banda ATR,
# pero dentro de la banda porcentual.
df_chico, ema = marco(102.05, 101.95, 102.0)
assert bool(_ema_band_mask(df_chico, ema, pct).iloc[-1]) is True
assert bool(_ema_band_mask(df_chico, ema, atr).iloc[-1]) is False

# ATR grande (1.00): el mismo 2 % son 2 ATR -> dentro de la banda ATR.
df_grande, ema = marco(102.5, 101.5, 102.0)
assert bool(_ema_band_mask(df_grande, ema, atr).iloc[-1]) is True

# Sin banda activa no filtra nada.
sin_banda = Params(use_ema_dist=False)
assert bool(_ema_band_mask(df_chico, ema, sin_banda).iloc[-1]) is True

# Los presets se optimizaron en % y deben forzar ese modo.
assert ui_values("OP/USDT:USDT")["dist_mode"] == "Porcentaje fijo"
assert ui_values("Actual (por defecto)")["dist_mode"] == "ATR adaptativo"

print("OK banda ATR")
