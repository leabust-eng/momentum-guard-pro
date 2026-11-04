from dataclasses import replace

import numpy as np

from engine import Params, _cusum, load_data, run_backtest


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
        f"{tag:<22} {m['total_return']*100:>8.2f} {m['n_trades']:>4d} "
        f"{m['profit_factor']:>6.2f} {m['max_dd']*100:>8.2f} "
        f"{m['win_rate']*100:>6.1f} {m['sharpe']:>7.2f} {m['exposure']*100:>7.1f}"
    )


def header(title):
    print()
    print(title)
    print(f"{'valor':<22} {'ret%':>8} {'ops':>4} {'PF':>6} {'dd%':>8} {'win%':>6} {'sharpe':>7} {'expo%':>7}")


df = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-07-24", "2026-11-01")
user = user_params()
print("AAVE 15m:", len(df), "velas |", df.index.min(), "->", df.index.max())

m = run_backtest(df, user).metrics
print(f"CONFIG USUARIO: ret% {m['total_return']*100:.2f} | ops {m['n_trades']} | "
      f"PF {m['profit_factor']:.2f} | dd% {m['max_dd']*100:.2f} | b&h% {m['buy_hold_return']*100:.2f}")

# --- Estadistica del disparador CUSUM -------------------------------------
up, dn, pend = _cusum(df, user)
n = len(df)
days = max((df.index[-1] - df.index[0]).days, 1)
print()
print("--- CUSUM config usuario ---")
print(f"eventos alcistas: {int(up.sum())} | bajistas: {int(dn.sum())} | "
      f"total: {int(up.sum()+dn.sum())} (~{(up.sum()+dn.sum())/days:.2f}/dia)")
print(f"velas con direccion armada: {int((pend != 0).sum())} ({(pend != 0).mean()*100:.1f}%)")

r = run_backtest(df, user)
entries = r.trades["entry_time"]
dists = []
for t in entries:
    i = df.index.get_loc(t)
    j = i
    while j >= 0 and pend[j] == 0:
        j -= 1
    dists.append(i - j if j >= 0 else -1)
dists = np.array(dists)
print(f"distancia evento->entrada (velas): mediana {np.median(dists):.0f} | "
      f"min {dists.min()} | max {dists.max()} | en la misma vela: {(dists == 0).sum()}/{len(dists)}")

# --- Sensibilidad ----------------------------------------------------------
for name, key, values in [
    ("threshold", "cusum_threshold", [1, 2, 3, 4, 5, 6, 8, 10, 12, 15]),
    ("drift", "cusum_drift", [0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]),
    ("vol_period", "cusum_vol_period", [5, 10, 20, 30, 40, 60, 80, 100]),
    ("pending_bars", "pending_bars", [1, 2, 3, 5, 10]),
]:
    header(f"--- {name} (resto = config usuario) ---")
    for v in values:
        mm = run_backtest(df, replace(user, **{key: v})).metrics
        line(f"{name}={v}", mm)

# --- CUSUM aislado: sin EMA/RSI/CHOP/ZLEMA ---------------------------------
iso = replace(
    user, use_ema=False, use_rsi=False, use_chop=False, use_zlag=False,
    use_ema_dist=False, require_color=False,
)
header("--- CUSUM aislado (sin filtros), threshold ---")
for v in [1, 2, 3, 5, 8, 10, 15]:
    mm = run_backtest(df, replace(iso, cusum_threshold=v)).metrics
    line(f"threshold={v}", mm)

header("--- CUSUM aislado, drift ---")
for v in [0.1, 0.25, 0.5, 1.0, 1.5, 2.0]:
    mm = run_backtest(df, replace(iso, cusum_drift=v)).metrics
    line(f"drift={v}", mm)

# --- Estabilidad por mitades (threshold) -----------------------------------
mid = df.index[len(df) // 2]
print()
print("--- Estabilidad por mitades (config usuario) ---")
for v in [2, 3, 5, 8, 10]:
    cfg = replace(user, cusum_threshold=v)
    a = run_backtest(df[df.index < mid], cfg).metrics
    b = run_backtest(df[df.index >= mid], cfg).metrics
    print(f"th={v:<3} 1a: {a['total_return']*100:>7.2f}% ({a['n_trades']} ops) | "
          f"2a: {b['total_return']*100:>7.2f}% ({b['n_trades']} ops)")
