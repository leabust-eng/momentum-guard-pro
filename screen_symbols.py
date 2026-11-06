"""Fase 1: prueba la configuración actual en todos los símbolos de la lista.

No optimiza nada: mide qué símbolos ya son rentables con los parámetros que usa
el usuario, separando entrenamiento (70%) y validación (30%) para detectar
sobreajuste desde el principio.
"""

import time

import pandas as pd

from engine import Params, find_earliest_bingx, load_data, run_backtest

SYMBOLS = [
    "AAVE/USDT:USDT",
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "BNB/USDT:USDT",
    "XRP/USDT:USDT",
    "DOGE/USDT:USDT",
    "AVAX/USDT:USDT",
    "LINK/USDT:USDT",
    "ADA/USDT:USDT",
    "LTC/USDT:USDT",
    "BCH/USDT:USDT",
    "OP/USDT:USDT",
]
END = "2026-11-06"
TRAIN_FRAC = 0.70

p = Params(
    initial_capital=3000.0,
    leverage=3.0,
    position_pct=1.0,
    commission=0.0005,
    slippage=0.0002,
    funding_rate_8h=0.0001,
    maintenance_margin=0.005,
)


def metrics_row(res) -> dict:
    m = res.metrics
    return {
        "ops": m["n_trades"],
        "ret": m["total_return"] * 100.0,
        "dd": m["max_dd"] * 100.0,
        "pf": m["profit_factor"],
        "win": m["win_rate"] * 100.0,
    }


rows = []
for sym in SYMBOLS:
    t0 = time.time()
    try:
        earliest = find_earliest_bingx(sym, "15m")
        df = load_data("bingx", sym, "15m", str(earliest.date()), END)
        split = df.index[int(len(df) * TRAIN_FRAC)]

        full = metrics_row(run_backtest(df, p))
        train = metrics_row(run_backtest(df[df.index < split], p))
        test = metrics_row(run_backtest(df, p, trade_start=split))

        row = {
            "simbolo": sym,
            "velas": len(df),
            "desde": f"{df.index.min():%Y-%m-%d}",
            "hasta": f"{df.index.max():%Y-%m-%d}",
            "split": f"{split:%Y-%m-%d}",
            **{f"full_{k}": v for k, v in full.items()},
            **{f"train_{k}": v for k, v in train.items()},
            **{f"test_{k}": v for k, v in test.items()},
        }
        row["robusto"] = (
            train["ret"] > 0
            and test["ret"] > 0
            and train["ops"] >= 5
            and test["ops"] >= 5
        )
        rows.append(row)
        print(
            f"{sym:<16} velas {len(df):>6} | full {full['ret']:+8.2f}% | "
            f"train {train['ret']:+8.2f}% ({train['ops']:>2} ops) | "
            f"test {test['ret']:+8.2f}% ({test['ops']:>2} ops) | "
            f"{'ROBUSTO' if row['robusto'] else ''} | {time.time() - t0:5.1f}s"
        )
    except Exception as exc:
        print(f"{sym:<16} ERROR {type(exc).__name__}: {exc}")

out = pd.DataFrame(rows).sort_values("test_ret", ascending=False)
out.to_csv("scanner_defaults.csv", index=False)
print("\nGuardado en scanner_defaults.csv")
print(
    out[
        [
            "simbolo",
            "full_ret",
            "train_ret",
            "test_ret",
            "test_ops",
            "test_dd",
            "test_pf",
            "robusto",
        ]
    ].to_string(index=False)
)
