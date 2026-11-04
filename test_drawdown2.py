import pandas as pd
from datetime import timedelta
from engine import Params, load_data, run_backtest

p = Params(position_pct=0.9)
dq = max(320, p.ema_len + 50, p.zlag_len * 3 + 50)
warm = int(-(-dq * 15 // 1440)) + 2
df = load_data("bingx", "AAVE/USDT:USDT", "15m",
               str((pd.Timestamp("2026-09-01") - timedelta(days=warm)).date()), "2026-11-04")
r = run_backtest(df, p, trade_start=pd.Timestamp("2026-09-01"))
eq = r.equity.dropna()

puntos = {
    "pico 02-10 04:45": "2026-10-02 04:45",
    "cierre #7 03-10 00:15": "2026-10-03 00:15",
    "entrada #8 06-10 09:15": "2026-10-06 09:15",
    "valle 06-10 12:45": "2026-10-06 12:45",
    "cierre #8 07-10 06:30": "2026-10-07 06:30",
}
vals = {}
for k, v in puntos.items():
    vals[k] = eq.loc[pd.Timestamp(v)]
    print(f"{k:<24} {vals[k]:>12,.2f}")

print(f"\ntramo A (devolución de ganancia flotante de #7): {vals['cierre #7 03-10 00:15'] - vals['pico 02-10 04:45']:>10,.2f}")
print(f"tramo B (flotante adverso de #8):                {vals['valle 06-10 12:45'] - vals['entrada #8 06-10 09:15']:>10,.2f}")
print(f"total pico->valle:                               {vals['valle 06-10 12:45'] - vals['pico 02-10 04:45']:>10,.2f}")
