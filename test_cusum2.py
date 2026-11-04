from dataclasses import replace

import numpy as np

import engine
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


def line(tag, m):
    print(
        f"{tag:<16} {m['total_return']*100:>8.2f} {m['n_trades']:>4d} "
        f"{m['profit_factor']:>6.2f} {m['max_dd']*100:>8.2f} "
        f"{m['win_rate']*100:>6.1f} {m['sharpe']:>7.2f} {m['exposure']*100:>7.1f}"
    )


def header(title):
    print()
    print(title)
    print(f"{'caso':<16} {'ret%':>8} {'ops':>4} {'PF':>6} {'dd%':>8} {'win%':>6} {'sharpe':>7} {'expo%':>7}")


df = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-07-26", "2026-11-02")
print("AAVE 15m:", len(df), "velas")

user = user_params()

# --- Sin CUSUM: direccion siempre armada ------------------------------------
orig = engine._cusum
n = len(df)
try:
    engine._cusum = lambda d, p: (
        np.zeros(len(d), dtype=bool),
        np.zeros(len(d), dtype=bool),
        np.ones(len(d), dtype=int),
    )
    header("--- Sin CUSUM vs con CUSUM (config usuario) ---")
    line("sin CUSUM", run_backtest(df, user).metrics)
    line("con CUSUM", run_backtest(df, user).metrics)
finally:
    engine._cusum = orig

# --- Transferencia a otros simbolos ---------------------------------------
for sym in ["ETH/USDT:USDT", "SOL/USDT:USDT"]:
    try:
        d2 = load_data("bingx", sym, "15m", "2026-07-26", "2026-11-02")
    except Exception as e:
        print(f"\n{sym}: no disponible ({e})")
        continue
    header(f"--- {sym} 15m, threshold (config usuario) ---")
    for v in [2, 3, 4, 5, 6, 8, 10]:
        line(f"threshold={v}", run_backtest(d2, replace(user, cusum_threshold=v)).metrics)
    m = run_backtest(d2, replace(user, cusum_threshold=5)).metrics
    print(f"b&h%: {m['buy_hold_return']*100:.2f} | velas: {len(d2)}")
