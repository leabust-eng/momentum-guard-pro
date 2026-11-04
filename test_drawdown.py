"""¿De dónde sale el max drawdown si solo hay 2 operaciones perdedoras?"""

from datetime import timedelta

import pandas as pd

from engine import Params, load_data, run_backtest

SYM, TF = "AAVE/USDT:USDT", "15m"
START = pd.Timestamp("2026-09-01")
END = pd.Timestamp("2026-11-04")

p = Params(position_pct=0.9)
dq = max(320, p.ema_len + 50, p.zlag_len * 3 + 50)
warm = int(-(-dq * 15 // 1440)) + 2

df = load_data("bingx", SYM, TF, str((START - timedelta(days=warm)).date()), str(END.date()))
res = run_backtest(df, p, trade_start=START)

eq = res.equity.dropna()
dd = eq / eq.cummax() - 1.0
trough = dd.idxmin()
peak = eq.loc[:trough].idxmax()

print("=== EQUITY (mark-to-market, vela a vela) ===")
print(f"max drawdown: {dd.min()*100:.2f}%")
print(f"pico:   {peak:%Y-%m-%d %H:%M} UTC  equity {eq.loc[peak]:,.2f}")
print(f"valle:  {trough:%Y-%m-%d %H:%M} UTC  equity {eq.loc[trough]:,.2f}")
print(f"caída:  {eq.loc[trough] - eq.loc[peak]:,.2f} USDT")

tr = res.trades
print("\n=== OPERACIONES CERRADAS ===")
print(f"{'#':>3} {'dir':<5} {'entrada':<16} {'salida':<16} {'pnl':>10} {'ret%':>7}")
for i, t in tr.iterrows():
    print(f"{i:>3} {t['direction']:<5} {t['entry_time']:%Y-%m-%d %H:%M} {t['exit_time']:%Y-%m-%d %H:%M} "
          f"{t['pnl']:>10.2f} {t['return_pct']*100:>7.2f}")

losses = tr[tr["pnl"] < 0]
print(f"\nperdedoras: {len(losses)} | suma {losses['pnl'].sum():,.2f} USDT "
      f"({losses['pnl'].sum() / p.initial_capital * 100:.2f}% del capital inicial)")

# equity realizada: capital + suma acumulada de pnl
realized = p.initial_capital + tr["pnl"].cumsum()
peak_r = realized.cummax()
dd_r = realized / peak_r - 1.0
print(f"max drawdown SOLO con operaciones cerradas: {dd_r.min()*100:.2f}%")

# qué operación estaba abierta en el valle
abierta = tr[(tr["entry_time"] <= trough) & (tr["exit_time"] >= trough)]
print("\n=== operación abierta en el valle ===")
for _, t in abierta.iterrows():
    print(f"{t['direction']} {t['entry_time']:%Y-%m-%d %H:%M} -> {t['exit_time']:%Y-%m-%d %H:%M} "
          f"| entrada {t['entry_price']:.2f} | PnL final {t['pnl']:.2f}")

# peor flotante durante el valle
for _, t in abierta.iterrows():
    seg = eq.loc[t["entry_time"]:t["exit_time"]]
    print(f"  equity al entrar: {seg.iloc[0]:,.2f} -> mínimo dentro de la operación: {seg.min():,.2f} "
          f"({(seg.min()/seg.iloc[0]-1)*100:.2f}%) | al salir: {seg.iloc[-1]:,.2f} ({t['pnl']:+.2f})")
