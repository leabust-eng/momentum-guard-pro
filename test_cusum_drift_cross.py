from dataclasses import replace

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

for sym in ["AAVE/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]:
    df = load_data("bingx", sym, "15m", "2026-07-26", "2026-11-02")
    print(f"\n{sym} ({len(df)} velas)")
    for d in [0.45, 0.5, 0.55, 0.6]:
        m = run_backtest(df, replace(u, cusum_drift=d)).metrics
        print(
            f"  drift={d:<4} ret% {m['total_return']*100:>7.2f} | ops {m['n_trades']:>2d} | "
            f"PF {m['profit_factor']:>5.2f} | dd% {m['max_dd']*100:>7.2f} | win% {m['win_rate']*100:>5.1f}"
        )
