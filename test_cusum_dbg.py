from dataclasses import replace

import numpy as np

import engine
from engine import Params, load_data, run_backtest
from test_cusum import user_params


def summarize(tag, df):
    r = run_backtest(df, user_params())
    m = r.metrics
    print(f"{tag}: bars={len(df)} {df.index.min()} -> {df.index.max()} | "
          f"ret%={m['total_return']*100:.2f} ops={m['n_trades']} "
          f"final={m['final_equity']:.2f} b&h%={m['buy_hold_return']*100:.2f}")


for end in ["2026-11-01", "2026-11-02"]:
    d = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-07-26", end)
    summarize(f"end={end}", d)

d1 = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-07-26", "2026-11-01")
d2 = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-07-26", "2026-11-02")
common = d1.index.intersection(d2.index)
print("velas comunes:", len(common), "| solo en d2:", len(d2.index.difference(d1.index)),
      "| solo en d1:", len(d1.index.difference(d2.index)))
diff = (d1.loc[common, "Close"] - d2.loc[common, "Close"]).abs()
print("max diff close en velas comunes:", float(diff.max()))

r = run_backtest(d2, user_params())
print("\ntrades d2:")
print(r.trades[["entry_time", "exit_time", "direction", "pnl", "exit_reason"]].to_string())

print("\n-- test monkeypatch --")
orig = engine._cusum
try:
    engine._cusum = lambda d, p: (np.zeros(len(d), bool), np.zeros(len(d), bool), np.zeros(len(d), int))
    r0 = run_backtest(d2, user_params())
    print("pending=0 -> ops:", r0.metrics["n_trades"], "ret%:", round(r0.metrics["total_return"] * 100, 2))
    engine._cusum = lambda d, p: (np.zeros(len(d), bool), np.zeros(len(d), bool), np.ones(len(d), int))
    r1 = run_backtest(d2, user_params())
    print("pending=1 -> ops:", r1.metrics["n_trades"], "ret%:", round(r1.metrics["total_return"] * 100, 2))
finally:
    engine._cusum = orig
