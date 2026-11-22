"""La pérdida neta aísla el resultado del precio de los gastos de operar."""

import numpy as np
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
t = res.trades

# 1. Cada operación trae el desglose precio / slippage / comisiones + funding.
for col in ("pnl_gross", "pnl_price", "fees", "slippage_cost"):
    assert col in t, col

# 2. Identidad contable: PnL final = precio puro − slippage − gastos.
assert np.allclose(
    t["pnl_gross"] - t["slippage_cost"] - t["fees"], t["pnl"], atol=1e-6
), (t["pnl_gross"] - t["slippage_cost"] - t["fees"] - t["pnl"]).abs().max()

# 3. La pérdida neta es la suma de los resultados negativos medidos solo por
#    precio, sin compensar con las ganadoras.
pg = t["pnl_gross"]
assert abs(m["gross_loss_price"] - abs(pg[pg <= 0].sum())) < 1e-6
assert m["gross_loss_price"] > 0
assert m["gross_profit_price"] == pg[pg > 0].sum()

# 4. Los gastos solo pueden empeorar a los perdedores, así que la pérdida sin
#    gastos nunca supera a la bruta.
assert m["gross_loss_price"] <= m["gross_loss"] + 1e-6
assert m["total_fees"] > 0
assert m["total_slippage"] > 0

# 5. Sin costes, ambas pérdidas son idénticas (no hay nada que descontar).
sin_costes = run_backtest(
    df,
    Params(
        **(
            BASE
            | dict(
                commission=0.0,
                slippage=0.0,
                apply_funding=False,
            )
        )
    ),
    trade_start=pd.Timestamp(df.index.min()),
)
mc = sin_costes.metrics
assert mc["total_fees"] == 0.0
assert mc["total_slippage"] == 0.0
assert abs(mc["gross_loss_price"] - mc["gross_loss"]) < 1e-9
assert all(np.isclose(sin_costes.trades["pnl_gross"], sin_costes.trades["pnl"]))

print(
    f"OK pérdida neta: {m['gross_loss_price']:.2f} USDT sin gastos vs "
    f"{m['gross_loss']:.2f} USDT bruta · gastos {m['total_fees']:.2f} + "
    f"slippage {m['total_slippage']:.2f}"
)
