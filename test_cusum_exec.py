from dataclasses import replace

from engine import load_data, run_backtest
from test_cusum_fine import user_params

df = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-07-26", "2026-11-02")
u = user_params()

for mode in ["close", "next_open"]:
    for th in [4.0, 4.5, 5.0, 5.5, 6.0]:
        m = run_backtest(df, replace(u, exec_mode=mode, cusum_threshold=th)).metrics
        print(
            f"{mode:<9} th={th:<4} ret% {m['total_return']*100:>7.2f} | "
            f"ops {m['n_trades']:>2d} | PF {m['profit_factor']:>5.2f} | "
            f"dd% {m['max_dd']*100:>7.2f} | win% {m['win_rate']*100:>5.1f}"
        )
