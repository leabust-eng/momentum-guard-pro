"""Verifica la posición abierta al final y que ya no se cierre artificialmente."""

import pandas as pd

from engine import Params, load_data, run_backtest

df = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-06-01", "2026-11-05")
df.index = df.index + pd.Timedelta(hours=-3)
print(f"última vela: {df.index.max():%Y-%m-%d %H:%M} | cierre {df['Close'].iloc[-1]:.2f}")

res = run_backtest(df, Params(initial_capital=3000.0, leverage=3.0, position_pct=1.0), trade_start=pd.Timestamp("2026-10-01"))
print(f"ops cerradas: {len(res.trades)} | equity final: {res.metrics['final_equity']:.2f}")
print(res.trades.tail(3)[["entry_time", "exit_time", "direction", "entry_price", "exit_price", "pnl", "exit_reason"]].to_string(index=False))
print("open_position:", res.open_position)
print(f"suma cerradas: {res.trades['pnl'].sum():+.2f} | flotante: {res.metrics['final_equity'] - 3000 - res.trades['pnl'].sum():+.2f}")
