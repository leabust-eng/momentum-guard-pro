"""Los defaults nuevos deben reproducir la config que el usuario tenía en pantalla."""

from datetime import timedelta

import pandas as pd

from engine import Params, load_data, run_backtest

symbol, tf = "AAVE/USDT:USDT", "15m"
start = pd.Timestamp("2026-09-01")
end = pd.Timestamp("2026-11-04")

params = Params()
warmup_bars = max(320, params.ema_len + 50, params.zlag_len * 3 + 50)
warmup_days = int(-(-warmup_bars * 15 // 1440)) + 2
load_start = start - timedelta(days=warmup_days)

df = load_data("bingx", symbol, tf, str(load_start.date()), str(end.date()))
df = df[df.index <= pd.Timestamp("2026-11-04 14:15")]
res = run_backtest(df, params, trade_start=start)
m = res.metrics
print("warmup velas:", len(df) - len(df[df.index >= start]))
print("ventana:", df[df.index >= start].index.min(), "->", df[df.index >= start].index.max())
for k in (
    "total_return", "max_dd", "profit_factor", "n_trades",
    "win_rate", "buy_hold_return", "exposure", "funding_paid", "final_equity",
):
    print(f"  {k}: {m.get(k)}")
