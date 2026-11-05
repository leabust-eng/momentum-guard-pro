"""Verifica la aritmética del retorno con 3.000 USDT y 3x (margen 100%)."""

import pandas as pd

from engine import Params, load_data, run_backtest

df = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-06-01", "2026-11-05")
df.index = df.index + pd.Timedelta(hours=-3)

p = Params(
    initial_capital=3000.0,
    leverage=3.0,
    position_pct=1.0,
    commission=0.0005,
    slippage=0.0002,
    funding_rate_8h=0.0001,
    maintenance_margin=0.005,
)
res = run_backtest(df, p, trade_start=pd.Timestamp("2026-10-01"))
m = res.metrics
t = res.trades

print(
    f"capital {m['initial_capital']:,.2f} | equity final {m['final_equity']:,.2f} | "
    f"ganancia {m['net_profit']:+,.2f} | retorno {m['total_return'] * 100:+.2f}% | "
    f"funding {m['total_funding']:+.2f}"
)
print(
    f"nocional por operación al inicio: "
    f"{m['initial_capital'] * p.position_pct * p.leverage:,.2f} USDT"
)
print()

t = t.copy()
t["mov_pct"] = (
    (t["exit_price"] / t["entry_price"] - 1.0)
    * t["direction"].map({"Long": 1, "Short": -1})
    * 100.0
)
t["nocional"] = t["notional"]
t["pnl_sobre_nocional"] = t["pnl"] / t["nocional"] * 100.0
print(
    t[
        [
            "entry_time",
            "direction",
            "entry_price",
            "exit_price",
            "mov_pct",
            "nocional",
            "pnl",
            "pnl_sobre_nocional",
            "return_pct",
            "funding_paid",
        ]
    ].to_string(index=False)
)
print()
print(f"suma pnl trades: {t['pnl'].sum():+,.2f}")
print(f"suma funding:    {t['funding_paid'].sum():+,.2f}")
print(f"equity final - capital: {m['final_equity'] - 3000:+,.2f}")
print(f"ganancia / 3000:  {m['net_profit'] / 3000 * 100:+.2f}%")
print(f"ganancia / 9000:  {m['net_profit'] / 9000 * 100:+.2f}%")
