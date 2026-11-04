import sys

import numpy as np
import pandas as pd

from engine import Params, _atr, _chop, _cusum, _ema, _rsi, _ztrend, load_data, run_backtest

pd.set_option("display.width", 200)

symbol = sys.argv[1] if len(sys.argv) > 1 else "BTC-USD"
interval = sys.argv[2] if len(sys.argv) > 2 else "4h"
start = sys.argv[3] if len(sys.argv) > 3 else "2024-11-01"
end = sys.argv[4] if len(sys.argv) > 4 else "2026-11-01"

df = load_data(symbol, interval, start, end)
p = Params()
close = df["Close"]
open_ = df["Open"]

ema_val = _ema(close, p.ema_len)
ema_up = ema_val > ema_val.shift(p.ema_slope_bars)
ema_dn = ema_val < ema_val.shift(p.ema_slope_bars)
rsi_val = _rsi(close, p.rsi_len)
chop_val = _chop(df, p.chop_len)

zlag_lag = int(np.floor((p.zlag_len - 1) / 2))
zlema = _ema(close + (close - close.shift(zlag_lag)), p.zlag_len)
zvol = _atr(df, p.zlag_len).rolling(p.zlag_len * 3).max() * p.zlag_mult
zt = _ztrend(close.to_numpy(float), zlema.to_numpy(float), zvol.to_numpy(float))
event_up, event_dn, pending = _cusum(df, p)

verde_act = close > open_
verde_prev = close.shift(1) > open_.shift(1)
ema_pos_l = (close > ema_val) & (close.shift(1) > ema_val.shift(1))
color_l = verde_act & verde_prev
dist = (close - ema_val).abs() / ema_val * 100
cond_dist = (dist >= p.min_ema_dist_pct) & (dist <= p.max_ema_dist_pct)
cond_ema_l = ema_pos_l & color_l & ema_up & cond_dist
cond_rsi_l = rsi_val < p.rsi_ob
cond_chop = chop_val < p.chop_max
cond_zlag_l = zt == 1

trig_l = (pending == 1) & cond_ema_l & cond_rsi_l & cond_chop & cond_zlag_l

print(f"{symbol} {interval} {start} -> {end}  bars={len(df)}")
print("dist percentiles:", np.nanpercentile(dist, [5, 25, 50, 75, 95]).round(2))
print("event_up", int(event_up.sum()), "pending==1", int((pending == 1).sum()))
print("cond_ema_l", int(cond_ema_l.sum()), "cond_dist", int(cond_dist.sum()), "color_l", int(color_l.sum()))
print("cond_rsi_l", int(cond_rsi_l.sum()), "cond_chop", int(cond_chop.sum()), "cond_zlag_l", int(cond_zlag_l.sum()))
print("trig_l", int(trig_l.sum()))

res = run_backtest(df, p)
print("--- backtest ---")
for k in ["final_equity", "total_return", "max_dd", "n_trades", "win_rate", "profit_factor", "buy_hold_return"]:
    print(f"{k:>18}: {res.metrics.get(k)}")
if len(res.trades):
    print(res.trades.tail(12).to_string())
