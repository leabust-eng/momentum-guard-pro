import numpy as np
import pandas as pd

from engine import Params, _atr, _chop, _cusum, _ema, _rsi, _ztrend, load_data

pd.set_option("display.width", 200)

df = load_data("BTC-USD", "1d", "2018-01-01", "2026-11-01")
p = Params()
close = df["Close"]
open_ = df["Open"]
high = df["High"]
low = df["Low"]

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
roja_act = close < open_
roja_prev = close.shift(1) < open_.shift(1)

ema_pos_l = (close > ema_val) & (close.shift(1) > ema_val.shift(1))
ema_pos_s = (close < ema_val) & (close.shift(1) < ema_val.shift(1))
color_l = verde_act & verde_prev
color_s = roja_act & roja_prev
dist = (close - ema_val).abs() / ema_val * 100
cond_dist = (dist >= p.min_ema_dist_pct) & (dist <= p.max_ema_dist_pct)

cond_ema_l = ema_pos_l & color_l & ema_up & cond_dist
cond_ema_s = ema_pos_s & color_s & ema_dn & cond_dist
cond_rsi_l = rsi_val < p.rsi_ob
cond_rsi_s = rsi_val > p.rsi_os
cond_chop = chop_val < p.chop_max
cond_zlag_l = zt == 1
cond_zlag_s = zt == -1

print("bars", len(df))
print("event_up", int(event_up.sum()), "event_dn", int(event_dn.sum()))
print("pending!=0", int((pending != 0).sum()), "pending==1", int((pending == 1).sum()), "pending==-1", int((pending == -1).sum()))
print("ema_up", int(ema_up.sum()), "ema_dn", int(ema_dn.sum()))
print("ema_pos_l", int(ema_pos_l.sum()), "color_l", int(color_l.sum()), "cond_dist", int(cond_dist.sum()))
print("cond_ema_l", int(cond_ema_l.sum()), "cond_ema_s", int(cond_ema_s.sum()))
print("rsi_l", int(cond_rsi_l.sum()), "rsi_s", int(cond_rsi_s.sum()), "chop", int(cond_chop.sum()))
print("zlag_l", int(cond_zlag_l.sum()), "zlag_s", int(cond_zlag_s.sum()))
print("dist stats")
print(dist.describe())
print("chop stats")
print(chop_val.describe())
print("rsi stats")
print(rsi_val.describe())

trig_l = (pending == 1) & cond_ema_l & cond_rsi_l & cond_chop & cond_zlag_l
trig_s = (pending == -1) & cond_ema_s & cond_rsi_s & cond_chop & cond_zlag_s
print("trig_l", int(trig_l.sum()), "trig_s", int(trig_s.sum()))
print("pending1 & zlag_l", int(((pending == 1) & cond_zlag_l).sum()))
print("pending1 & ema_l", int(((pending == 1) & cond_ema_l).sum()))
print("pending1 & rsi_l", int(((pending == 1) & cond_rsi_l).sum()))
print("pending1 & chop", int(((pending == 1) & cond_chop).sum()))
print("pending1 & ema_l & rsi_l", int(((pending == 1) & cond_ema_l & cond_rsi_l).sum()))
print("pending1 & ema_l & chop", int(((pending == 1) & cond_ema_l & cond_chop).sum()))
print("pending1 & zlag_l & ema_l", int(((pending == 1) & cond_zlag_l & cond_ema_l).sum()))
