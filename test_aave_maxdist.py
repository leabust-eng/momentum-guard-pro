from dataclasses import replace

from engine import Params, load_data, run_backtest

df = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-07-24", "2026-11-01")
print("bars:", len(df), df.index.min(), "->", df.index.max())
print()

base = Params()
print(f"{'maxdist':>7} {'ret%':>8} {'dd%':>8} {'PF':>6} {'ops':>4} {'win%':>6} {'sharpe':>7} {'equity':>10}")
for d in [1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3.0, 4.0]:
    r = run_backtest(df, replace(base, max_ema_dist_pct=d))
    m = r.metrics
    print(
        f"{d:>7.1f} {m['total_return']*100:>8.2f} {m['max_dd']*100:>8.2f} "
        f"{m['profit_factor']:>6.2f} {m['n_trades']:>4d} {m['win_rate']*100:>6.1f} "
        f"{m['sharpe']:>7.2f} {m['final_equity']:>10.2f}"
    )

print()
r = run_backtest(df, replace(base, max_ema_dist_pct=1.6))
m = r.metrics
print("--- detalle maxdist=1.6 ---")
print(
    "ret%:", round(m["total_return"] * 100, 2),
    "| dd%:", round(m["max_dd"] * 100, 2),
    "| PF:", round(m["profit_factor"], 2),
    "| ops:", m["n_trades"],
    "| win%:", round(m["win_rate"] * 100, 1),
    "| sharpe:", round(m["sharpe"], 2),
    "| cagr%:", round(m["cagr"] * 100, 1),
    "| b&h%:", round(m["buy_hold_return"] * 100, 2),
    "| funding:", round(m["total_funding"], 2),
    "| liq:", m["liquidations"],
    "| expo%:", round(m["exposure"] * 100, 1),
)
print()
print(r.trades[["entry_time", "exit_time", "direction", "pnl", "exit_reason"]].to_string())
