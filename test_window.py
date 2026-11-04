from dataclasses import replace

import pandas as pd

from engine import Params, load_data, run_backtest

BASE = dict(
    cusum_vol_period=30, cusum_drift=0.5, cusum_threshold=5, pending_bars=1,
    use_ema=True, ema_len=200, ema_slope_bars=1, require_2bars=False,
    require_color=True, use_ema_dist=True, min_ema_dist_pct=1,
    max_ema_dist_pct=2, use_rsi=True, rsi_len=14, rsi_ob=75, rsi_os=20,
    use_chop=True, chop_len=14, chop_max=50, use_zlag=True, zlag_len=70,
    zlag_mult=2.2, trade_dir="Ambos", one_way=True, sl_pct=0.04, use_ts=True,
    ts_act_pct=0.02, ts_atr_len=14, ts_atr_mult=6, leverage=1,
    position_pct=0.9, maintenance_margin=0.005, apply_funding=True,
    funding_rate_8h=0.0001, initial_capital=10000, commission=0.0005,
    slippage=0.0002, exec_mode="close",
)
u = Params(**BASE)

df_all = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-07-20", "2026-11-03")
print("total:", len(df_all), df_all.index.min(), "->", df_all.index.max())

for start in ["2026-09-01", "2026-10-04"]:
    ts = pd.Timestamp(start)
    r = run_backtest(df_all, u, trade_start=ts)
    m = r.metrics
    print(f"\nventana {start}:")
    print(f"  equity: {r.equity.index.min()} -> {r.equity.index.max()} ({len(r.equity)} velas)")
    print(f"  ret% {m['total_return']*100:.2f} | ops {m['n_trades']} | PF {m['profit_factor']:.2f} | "
          f"dd% {m['max_dd']*100:.2f} | b&h% {m['buy_hold_return']*100:.2f} | "
          f"expo% {m['exposure']*100:.1f}")
    print("  NaNs:", int(r.equity.isna().sum()))
    if len(r.trades):
        print("  primer trade:", r.trades.iloc[0]["entry_time"],
              "| último:", r.trades.iloc[-1]["exit_time"])
        print("  trades antes del inicio:", int((r.trades["entry_time"] < ts).sum()))

# Sin warm-up: cargar solo desde 2026-10-04
df_short = df_all[df_all.index >= pd.Timestamp("2026-10-04")]
r2 = run_backtest(df_short, u)
m2 = r2.metrics
print(f"\nsin warm-up (solo 30d): ret% {m2['total_return']*100:.2f} | ops {m2['n_trades']} | "
      f"PF {m2['profit_factor']:.2f} | dd% {m2['max_dd']*100:.2f}")

# Regresión: ventana completa sin trade_start
r3 = run_backtest(df_all, u)
print(f"\ncompleto: ret% {r3.metrics['total_return']*100:.2f} | ops {r3.metrics['n_trades']} | "
      f"PF {r3.metrics['profit_factor']:.2f}")
