"""Regresión: pérdida bruta y drawdown en USDT en las métricas del motor."""

import pandas as pd

from engine import Params, load_data, run_backtest

BASE = dict(
    initial_capital=3000.0,
    leverage=3.0,
    position_pct=0.9,
    commission=0.0005,
    slippage=0.0002,
    funding_rate_8h=0.0001,
    maintenance_margin=0.005,
)

df = load_data("BingX Perpetuos", "AAVE/USDT:USDT", "15m", "2026-07-27", "2026-11-12")
res = run_backtest(df, Params(**BASE), trade_start=pd.Timestamp(df.index.min()))
m = res.metrics
pnl = res.trades["pnl"]

# La pérdida bruta es exactamente la suma de las operaciones cerradas en negativo
# (sin compensar con las ganadoras) y el profit factor es su cociente.
assert m["gross_loss"] == abs(pnl[pnl <= 0].sum()), m["gross_loss"]
assert m["gross_profit"] == pnl[pnl > 0].sum(), m["gross_profit"]
assert m["gross_loss"] > 0
assert abs(m["profit_factor"] - m["gross_profit"] / m["gross_loss"]) < 1e-9

# Peor operación = mínimo PnL.
assert m["worst_trade"] == pnl.min(), m["worst_trade"]
assert m["worst_trade"] <= 0

# El drawdown en dólares acompaña al porcentual y no puede ser positivo.
assert m["max_dd_usdt"] <= 0
assert m["max_dd_usdt"] < 0
assert m["max_dd"] <= 0
assert m["max_dd_closed_usdt"] <= 0

# Coherencia del drawdown en USD: corresponde a la misma caída que el porcentual
# (mismo valle), así que puede ser menor que la mayor caída absoluta en dinero.
eq = res.equity.dropna()
dd_serie = eq / eq.cummax() - 1.0
i = dd_serie.idxmin()
assert abs(m["max_dd"] - dd_serie.loc[i]) < 1e-12
assert abs(m["max_dd_usdt"] - (eq.loc[i] - eq.cummax().loc[i])) < 1e-6
assert m["max_dd_usdt"] <= 0
assert abs(m["max_dd_usdt"]) <= abs((eq - eq.cummax()).min()) + 1e-9

print(
    f"OK perdida bruta: {m['gross_loss']:.2f} USDT en "
    f"{m['n_losses']} perdedoras · peor {m['worst_trade']:.2f} · "
    f"DD {m['max_dd']*100:.2f} % ({m['max_dd_usdt']:.2f} USDT) · "
    f"DD cerradas {m['max_dd_closed']*100:.2f} % "
    f"({m['max_dd_closed_usdt']:.2f} USDT)"
)
