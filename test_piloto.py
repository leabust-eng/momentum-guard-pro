"""Piloto: rentabilidad con la config actual en varios símbolos (15m)."""

import time

import pandas as pd

from engine import Params, find_earliest_bingx, load_data, run_backtest

SYMBOLS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
END = "2026-11-06"

p = Params(
    initial_capital=3000.0,
    leverage=3.0,
    position_pct=1.0,
    commission=0.0005,
    slippage=0.0002,
    funding_rate_8h=0.0001,
    maintenance_margin=0.005,
)

for sym in SYMBOLS:
    t0 = time.time()
    earliest = find_earliest_bingx(sym, "15m")
    df = load_data("bingx", sym, "15m", str(earliest.date()), END)
    res = run_backtest(df, p)
    m = res.metrics
    print(
        f"{sym:<16} velas {len(df):>6} | {df.index.min():%Y-%m-%d} -> {df.index.max():%Y-%m-%d} | "
        f"ops {m['n_trades']:>3} | ret {m['total_return'] * 100:+7.2f}% | "
        f"DD {m['max_dd'] * 100:6.2f}% | PF {m['profit_factor']:5.2f} | "
        f"aciertos {m['win_rate'] * 100:5.1f}% | {time.time() - t0:5.1f}s"
    )
    if res.open_position is not None:
        print(f"   abierta: {res.open_position['direction']} desde {res.open_position['entry_time']}")
