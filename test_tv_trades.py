"""Compara las últimas operaciones de la app (UTC) con la lista de TradingView (UTC-3)."""

from datetime import timedelta

import pandas as pd

from engine import Params, load_data, run_backtest

SYM, TF = "AAVE/USDT:USDT", "15m"
END = pd.Timestamp("2026-11-04")

params = Params(position_pct=0.9)
warmup_bars = max(320, params.ema_len + 50, params.zlag_len * 3 + 50)
warmup_days = int(-(-warmup_bars * 15 // 1440)) + 2

df = load_data("bingx", SYM, TF, str((pd.Timestamp("2026-08-31") - timedelta(days=warmup_days)).date()), str(END.date()))


def show(start):
    res = run_backtest(df, params, trade_start=pd.Timestamp(start))
    tr = res.trades
    print(f"\n=== ventana desde {start} | {len(tr)} operaciones ===")
    print(f"{'#':>3} {'dir':<5} {'entrada UTC':<17} {'entrada UTC-3':<17} "
          f"{'salida UTC':<17} {'salida UTC-3':<17} {'px in':>9} {'px out':>9} {'pnl':>9}")
    for i, t in tr.iterrows():
        et, xt = t["entry_time"], t["exit_time"]
        print(f"{i:>3} {t['direction']:<5} {et:%Y-%m-%d %H:%M}   "
              f"{(et - timedelta(hours=3)):%Y-%m-%d %H:%M}   "
              f"{xt:%Y-%m-%d %H:%M}   {(xt - timedelta(hours=3)):%Y-%m-%d %H:%M}   "
              f"{t['entry_price']:>9.2f} {t['exit_price']:>9.2f} {t['pnl']:>9.2f}")


show("2026-08-31")
show("2026-09-01")
