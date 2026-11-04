from dataclasses import replace

from engine import Params, load_data, run_backtest


def user_params(**kw) -> Params:
    base = dict(
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
    base.update(kw)
    return Params(**base)


df = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-07-26", "2026-11-02")
u = user_params()

print("--- threshold fino ---")
for v in [3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0]:
    m = run_backtest(df, replace(u, cusum_threshold=v)).metrics
    print(f"th={v:<4} ret% {m['total_return']*100:>7.2f} | ops {m['n_trades']:>2d} | "
          f"PF {m['profit_factor']:>5.2f} | dd% {m['max_dd']*100:>7.2f}")

print("\n--- drift fino ---")
for v in [0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65]:
    m = run_backtest(df, replace(u, cusum_drift=v)).metrics
    print(f"drift={v:<4} ret% {m['total_return']*100:>7.2f} | ops {m['n_trades']:>2d} | "
          f"PF {m['profit_factor']:>5.2f} | dd% {m['max_dd']*100:>7.2f}")

print("\n--- concentracion de beneficios (config usuario) ---")
r = run_backtest(df, u)
pnl = r.trades["pnl"].sort_values(ascending=False)
total = pnl.sum()
print("neto:", round(total, 2), "| top1:", round(pnl.iloc[0], 2),
      f"({pnl.iloc[0]/total*100:.0f}% del neto)",
      "| top3:", round(pnl.iloc[:3].sum(), 2),
      f"({pnl.iloc[:3].sum()/total*100:.0f}%)",
      "| top5:", round(pnl.iloc[:5].sum(), 2),
      f"({pnl.iloc[:5].sum()/total*100:.0f}%)")
print("trades ganadores:", int((pnl > 0).sum()), "| perdedores:", int((pnl < 0).sum()))
print("mejor:", round(pnl.iloc[0], 2), "| peor:", round(pnl.iloc[-1], 2))
