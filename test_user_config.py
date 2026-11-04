from dataclasses import replace

from engine import Params, load_data, run_backtest

df = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-07-24", "2026-11-01")

user = Params(
    cusum_vol_period=30,
    cusum_drift=0.5,
    cusum_threshold=5,
    pending_bars=1,
    use_ema=True,
    ema_len=200,
    ema_slope_bars=1,
    require_2bars=False,
    require_color=True,
    use_ema_dist=True,
    min_ema_dist_pct=1,
    max_ema_dist_pct=2,
    use_rsi=True,
    rsi_len=14,
    rsi_ob=75,
    rsi_os=20,
    use_chop=True,
    chop_len=14,
    chop_max=50,
    use_zlag=True,
    zlag_len=70,
    zlag_mult=2.2,
    trade_dir="Ambos",
    one_way=True,
    sl_pct=0.04,
    use_ts=True,
    ts_act_pct=0.02,
    ts_atr_len=14,
    ts_atr_mult=6,
    leverage=1,
    position_pct=0.9,
    maintenance_margin=0.005,
    apply_funding=True,
    funding_rate_8h=0.0001,
    initial_capital=10000,
    commission=0.0005,
    slippage=0.0002,
    exec_mode="close",
)

default = Params()

m = run_backtest(df, user).metrics
print("CONFIG USUARIO -> ret%:", round(m["total_return"] * 100, 2),
      "| dd%:", round(m["max_dd"] * 100, 2),
      "| PF:", round(m["profit_factor"], 2),
      "| ops:", m["n_trades"],
      "| win%:", round(m["win_rate"] * 100, 1),
      "| sharpe:", round(m["sharpe"], 2))
print()

changed = {
    "cusum_vol_period": (20, 30),
    "pending_bars": (3, 1),
    "ema_slope_bars": (2, 1),
    "require_2bars": (True, False),
    "max_ema_dist_pct": (4.0, 2.0),
    "rsi_os": (30, 20),
    "chop_max": (45, 50),
    "zlag_mult": (1.2, 2.2),
    "position_pct": (1.0, 0.9),
}

print("Leave-one-out: se revierte cada parámetro a su valor por defecto")
print(f"{'param':<20} {'ret%':>8} {'ops':>4} {'PF':>6} {'dd%':>8} {'win%':>6}")
for key, (dflt, used) in changed.items():
    cfg = replace(user, **{key: dflt})
    mm = run_backtest(df, cfg).metrics
    print(f"{key:<20} {mm['total_return']*100:>8.2f} {mm['n_trades']:>4d} "
          f"{mm['profit_factor']:>6.2f} {mm['max_dd']*100:>8.2f} {mm['win_rate']*100:>6.1f}")
print()

print("Solo max_ema_dist_pct=2.0 sobre defaults")
cfg = replace(default, max_ema_dist_pct=2.0)
mm = run_backtest(df, cfg).metrics
print("ret%:", round(mm["total_return"] * 100, 2), "| ops:", mm["n_trades"],
      "| PF:", round(mm["profit_factor"], 2), "| dd%:", round(mm["max_dd"] * 100, 2))
