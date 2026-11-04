"""Retorno con la configuración validada del usuario, por ventana de análisis."""

from datetime import date, timedelta

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
U = Params(**BASE)

df = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-07-20", "2026-11-03")
first = df.index.min()
last = df.index.max()
print(f"datos: {len(df)} velas | {first} -> {last}\n")

today = date(2026, 11, 3)
windows = [("Histórico completo", None)]
for days in (7, 30, 60, 90):
    windows.append((f"Últimos {days} días", today - timedelta(days=days)))

rows = []
for label, start in windows:
    if start is None:
        r = run_backtest(df, U)
    else:
        r = run_backtest(df, U, trade_start=pd.Timestamp(start))
    m = r.metrics
    rows.append(
        {
            "ventana": label,
            "desde": r.equity.index.min().date().isoformat(),
            "retorno_%": round(m["total_return"] * 100, 2),
            "ops": m["n_trades"],
            "pf": round(m["profit_factor"], 2),
            "dd_%": round(m["max_dd"] * 100, 2),
            "bh_%": round(m["buy_hold_return"] * 100, 2),
            "expo_%": round(m["exposure"] * 100, 1),
        }
    )

print(pd.DataFrame(rows).to_string(index=False))
