"""Chequeo rápido de un símbolo con la config actual y en 3 bloques."""

import sys

import pandas as pd

from engine import find_earliest_bingx, load_data, run_backtest
from validate_presets import DEFAULT, block_stats, build

sym = sys.argv[1] if len(sys.argv) > 1 else "AXS/USDT:USDT"
earliest = find_earliest_bingx(sym, "15m")
df = load_data("bingx", sym, "15m", str(earliest.date()), "2026-11-06")
idx = df.index
cuts = [idx[0], idx[len(idx) // 3], idx[2 * len(idx) // 3], idx[-1] + pd.Timedelta(minutes=15)]

print(f"{sym}  {idx[0]:%Y-%m-%d} -> {idx[-1]:%Y-%m-%d}  ({len(df)} velas)")
for k in range(3):
    ops, ret, pf = block_stats(df, build(DEFAULT), cuts[k], cuts[k + 1])
    print(f"  B{k + 1}: {ret:+8.2f}% ({ops} ops, PF {pf:.2f})")

res = run_backtest(df, build(DEFAULT))
m = res.metrics
print(
    f"  TOTAL: {m['total_return'] * 100:+.2f}% | ops {m['n_trades']} | "
    f"PF {m['profit_factor']:.2f} | DD {m['max_dd'] * 100:.2f}% | "
    f"win {m['win_rate'] * 100:.1f}%"
)
if res.open_position:
    op = res.open_position
    print(f"  abierta: {op['direction']} desde {op['entry_time']}")
