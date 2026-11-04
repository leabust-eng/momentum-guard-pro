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
U = Params(**BASE)
TH = [3.0, 4.0, 4.5, 5.0, 5.5, 6.0, 7.0, 8.0]
DR = [0.4, 0.45, 0.5, 0.55, 0.6, 0.7]

df = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-07-26", "2026-11-02")
print(f"AAVE 15m: {len(df)} velas | {df.index.min()} -> {df.index.max()}")

FOLDS = [
    ("2026-08-16", "2026-09-06"),
    ("2026-09-06", "2026-09-27"),
    ("2026-09-27", "2026-10-18"),
    ("2026-10-18", "2026-11-02"),
]


def score(m):
    if m["n_trades"] < 5:
        return -1e9
    return m["total_return"] / max(abs(m["max_dd"]), 0.005)


def fmt(m):
    return (
        f"ret {m['total_return']*100:>7.2f}% | PF {m['profit_factor']:>5.2f} | "
        f"DD {m['max_dd']*100:>7.2f}% | ops {m['n_trades']:>2d} | "
        f"win {m['win_rate']*100:>5.1f}%"
    )


fixed_rets, adapt_rets = [], []
chosen = []

for k, (tea, teb) in enumerate(FOLDS, 1):
    train = df[df.index < tea]
    test = df[(df.index >= tea) & (df.index < teb)]
    print()
    print("=" * 78)
    print(f"FOLD {k}: train {train.index.min().date()} -> {tea} ({len(train)} velas)")
    print(f"          test {tea} -> {teb} ({len(test)} velas)")

    rows = []
    for th in TH:
        for dr in DR:
            m = run_backtest(train, replace(U, cusum_threshold=th, cusum_drift=dr)).metrics
            rows.append((score(m), th, dr, m))
    rows.sort(key=lambda x: x[0], reverse=True)

    bests = rows[:3]
    print("  top 3 en train (score = retorno / |DD|, mínimo 5 ops):")
    for s, th, dr, m in bests:
        print(f"    th={th:<4} drift={dr:<4} score={s:>6.2f} | {fmt(m)}")

    s, th, dr, mtr = rows[0]
    chosen.append((th, dr))
    print(f"  ELEGIDO: th={th} drift={dr}")
    print(f"    train: {fmt(mtr)}")

    m_adapt = run_backtest(test, replace(U, cusum_threshold=th, cusum_drift=dr)).metrics
    m_fixed = run_backtest(test, U).metrics
    adapt_rets.append(m_adapt["total_return"])
    fixed_rets.append(m_fixed["total_return"])
    print(f"    test adaptativo: {fmt(m_adapt)}")
    print(f"    test fijo 5/0.5: {fmt(m_fixed)}")

print()
print("=" * 78)
print("RESUMEN")
for k, ((th, dr), fr, ar) in enumerate(zip(chosen, fixed_rets, adapt_rets), 1):
    print(f"fold {k}: elegido th={th:<4} drift={dr:<4} | fijo {fr*100:>7.2f}% | "
          f"adaptativo {ar*100:>7.2f}%")

comp_fixed = 1.0
comp_adapt = 1.0
for r in fixed_rets:
    comp_fixed *= 1 + r
for r in adapt_rets:
    comp_adapt *= 1 + r
print(f"\nfijo 5/0.5: retorno compuesto test = {(comp_fixed-1)*100:.2f}% | "
      f"folds positivos {sum(r > 0 for r in fixed_rets)}/{len(fixed_rets)}")
print(f"adaptativo:  retorno compuesto test = {(comp_adapt-1)*100:.2f}% | "
      f"folds positivos {sum(r > 0 for r in adapt_rets)}/{len(adapt_rets)}")
print(f"threshold elegido: {[c[0] for c in chosen]}")
print(f"drift elegido:     {[c[1] for c in chosen]}")
