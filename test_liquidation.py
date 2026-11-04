import numpy as np

from engine import Params, load_data, run_backtest

df = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-07-24", "2026-11-01")

p = Params(leverage=20, position_pct=1.0, sl_pct=0.15, use_ts=False)
r = run_backtest(df, p)
m = r.metrics
print("ret%:", round(m["total_return"] * 100, 2),
      "| final:", round(m["final_equity"], 2),
      "| liq:", m["liquidations"],
      "| ops:", m["n_trades"],
      "| dd%:", round(m["max_dd"] * 100, 2),
      "| sharpe:", m["sharpe"],
      "| cagr:", m["cagr"])
print("NaNs en equity:", int(r.equity.isna().sum()))
print("min equity:", float(r.equity.min()), "| last:", float(r.equity.iloc[-1]))

if m["liquidations"]:
    t = r.trades[r.trades["exit_reason"] == "liquidation"]
    print("primer liquidacion:", t.iloc[0]["exit_time"])
    print("operaciones despues de la liquidacion:",
          int((r.trades["entry_time"] > t.iloc[0]["exit_time"]).sum()))
    print("equity en la vela de liquidacion:",
          float(r.equity.loc[t.iloc[0]["exit_time"]]))
    print("equity max despues de la liquidacion:",
          float(r.equity.loc[r.equity.index > t.iloc[0]["exit_time"]].max()))
