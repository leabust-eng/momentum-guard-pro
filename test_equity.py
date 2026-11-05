"""Descompone el equity final en precio, slippage, comisiones y funding."""

import pandas as pd

from engine import Params, load_data, run_backtest

df = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-06-01", "2026-11-05")
df.index = df.index + pd.Timedelta(hours=-3)

p = Params(
    initial_capital=3000.0,
    leverage=3.0,
    position_pct=1.0,
    commission=0.0005,
    slippage=0.0002,
    funding_rate_8h=0.0001,
    maintenance_margin=0.005,
)
res = run_backtest(df, p, trade_start=pd.Timestamp("2026-10-01"))
t = res.trades.copy()
m = res.metrics

t["dir"] = t["direction"].map({"Long": 1, "Short": -1})
# Precio "puro" del disparador, deshaciendo el slippage que aplica _enter/_exit.
t["raw_entry"] = t["entry_price"] / (1.0 + t["dir"] * p.slippage)
t["raw_exit"] = t["exit_price"] / (1.0 - t["dir"] * p.slippage)
t["bruto_precio"] = t["dir"] * t["units"] * (t["raw_exit"] - t["raw_entry"])
t["bruto_fills"] = t["dir"] * t["units"] * (t["exit_price"] - t["entry_price"])
t["slippage"] = t["bruto_fills"] - t["bruto_precio"]
t["comision_entrada"] = t["notional"] * p.commission
t["comision_salida"] = t["units"] * t["exit_price"] * p.commission
t["comisiones"] = t["comision_entrada"] + t["comision_salida"]
t["funding_costo"] = t["funding_paid"]
t["neto_check"] = (
    t["bruto_precio"] + t["slippage"] - t["comisiones"] - t["funding_costo"]
)

cols = [
    "entry_time",
    "bruto_precio",
    "slippage",
    "comisiones",
    "funding_costo",
    "neto_check",
    "pnl",
]
print(t[cols].to_string(index=False))
print()
print(f"capital inicial:          {p.initial_capital:+,.2f}")
print(f"bruto por precio:         {t['bruto_precio'].sum():+,.2f}")
print(f"slippage:                 {t['slippage'].sum():+,.2f}")
print(f"comisiones:               {-t['comisiones'].sum():+,.2f}")
print(f"funding (neto):           {-t['funding_costo'].sum():+,.2f}")
print(f"suma trades:              {t['pnl'].sum():+,.2f}")
print(f"flotante / residual:      {m['final_equity'] - 3000 - t['pnl'].sum():+,.2f}")
print(f"equity final:             {m['final_equity']:+,.2f}")
print(f"error de redondeo:        {t['neto_check'].sum() - t['pnl'].sum():+.6f}")
