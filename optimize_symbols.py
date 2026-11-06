"""Fase 2: búsqueda controlada de parámetros por símbolo, con validación fuera
de muestra y chequeo de estabilidad.

Metodología:
- 70% de los datos para buscar (train), 30% para validar (test).
- Se prueban combinaciones al azar de un espacio acotado de parámetros.
- Se conservan las mejores por train y se validan en test.
- Se exige que el test sea positivo, con operaciones suficientes y que los
  parámetros vecinos también funcionen (meseta, no pico aislado).

No garantiza rentabilidad futura: con ~100 días de 15m, esto es un filtro para
descartar, no una prueba definitiva.
"""

import argparse
import json
import random
import time
from dataclasses import replace

import numpy as np
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
    "AXS/USDT:USDT",
]

SPACE = {
    "cusum_threshold": [3.0, 4.0, 5.0, 6.0, 7.0],
    "cusum_drift": [0.3, 0.5, 0.7],
    "pending_bars": [1, 2],
    "ema_band": [(0.5, 1.5), (1.0, 1.6), (1.0, 2.0), (1.5, 2.5)],
    "rsi_ob": [70.0, 75.0, 80.0],
    "rsi_os": [20.0, 25.0, 30.0],
    "chop_max": [40.0, 45.0, 50.0, 55.0],
    "zlag_len": [50, 70, 90],
    "zlag_mult": [1.8, 2.2, 2.6],
    "sl_pct": [0.02, 0.03, 0.04, 0.05, 0.06],
    "ts_act_pct": [0.01, 0.02, 0.03],
    "ts_atr_mult": [4.0, 6.0, 8.0],
}

BASE = Params(
    initial_capital=3000.0,
    leverage=3.0,
    position_pct=1.0,
    commission=0.0005,
    slippage=0.0002,
    funding_rate_8h=0.0001,
    maintenance_margin=0.005,
)

DEFAULT_COMBO = {
    "cusum_threshold": 5.0,
    "cusum_drift": 0.5,
    "pending_bars": 1,
    "ema_band": (1.0, 1.6),
    "rsi_ob": 75.0,
    "rsi_os": 20.0,
    "chop_max": 50.0,
    "zlag_len": 70,
    "zlag_mult": 2.2,
    "sl_pct": 0.04,
    "ts_act_pct": 0.02,
    "ts_atr_mult": 6.0,
}


def build_params(combo: dict) -> Params:
    lo, hi = combo["ema_band"]
    return replace(
        BASE,
        cusum_threshold=combo["cusum_threshold"],
        cusum_drift=combo["cusum_drift"],
        pending_bars=combo["pending_bars"],
        min_ema_dist_pct=lo,
        max_ema_dist_pct=hi,
        rsi_ob=combo["rsi_ob"],
        rsi_os=combo["rsi_os"],
        chop_max=combo["chop_max"],
        zlag_len=combo["zlag_len"],
        zlag_mult=combo["zlag_mult"],
        sl_pct=combo["sl_pct"],
        ts_act_pct=combo["ts_act_pct"],
        ts_atr_mult=combo["ts_atr_mult"],
    )


def evaluate(df: pd.DataFrame, combo: dict, start=None) -> dict:
    res = run_backtest(df, build_params(combo), trade_start=start)
    m = res.metrics
    return {
        "ret": m["total_return"] * 100.0,
        "dd": m["max_dd"] * 100.0,
        "pf": m["profit_factor"],
        "ops": m["n_trades"],
        "win": m["win_rate"] * 100.0,
    }


def score(m: dict) -> float:
    if m["ops"] < 6 or not np.isfinite(m["pf"]) or m["pf"] < 1.05:
        return -1e9
    if m["ret"] <= 0:
        return -1e9
    dd = max(abs(m["dd"]), 2.0)
    return m["ret"] / dd


def random_combos(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    combos = [dict(DEFAULT_COMBO)]
    seen = {tuple(DEFAULT_COMBO[k] for k in SPACE)}
    while len(combos) < n:
        c = {k: rng.choice(v) for k, v in SPACE.items()}
        key = tuple(c[k] for k in SPACE)
        if key in seen:
            continue
        seen.add(key)
        combos.append(c)
    return combos


def neighbors(combo: dict) -> list[dict]:
    out = []
    for key, values in SPACE.items():
        idx = values.index(combo[key])
        for j in (idx - 1, idx + 1):
            if 0 <= j < len(values):
                c = dict(combo)
                c[key] = values[j]
                out.append(c)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=120)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--symbols", nargs="*", default=SYMBOLS)
    ap.add_argument("--out", default="optimizer_results.csv")
    args = ap.parse_args()

    rows = []
    for sym in args.symbols:
        t0 = time.time()
        try:
            earliest = find_earliest_bingx(sym, "15m")
            df = load_data("bingx", sym, "15m", str(earliest.date()), "2026-11-06")
        except Exception as exc:
            print(f"{sym}: ERROR datos {type(exc).__name__}: {exc}")
            continue

        split = df.index[int(len(df) * 0.70)]
        train_df = df[df.index < split]
        default_train = evaluate(train_df, DEFAULT_COMBO)
        default = evaluate(df, DEFAULT_COMBO, start=split)

        scored = []
        for combo in random_combos(args.samples, args.seed):
            m = evaluate(train_df, combo)
            s = score(m)
            if s > -1e8:
                scored.append((s, combo, m))
        scored.sort(key=lambda x: x[0], reverse=True)

        candidates = [
            {
                "combo": dict(DEFAULT_COMBO),
                "train": default_train,
                "test": default,
                "score_test": score(default),
            }
        ]
        for s_train, combo, m_train in scored[: args.top]:
            if combo == DEFAULT_COMBO:
                continue
            m_test = evaluate(df, combo, start=split)
            candidates.append(
                {
                    "combo": combo,
                    "train": m_train,
                    "test": m_test,
                    "score_test": score(m_test),
                }
            )
        candidates.sort(key=lambda x: x["score_test"], reverse=True)

        best = candidates[0]
        es_default = best["combo"] == DEFAULT_COMBO
        mejora = best["test"]["ret"] - default["ret"]
        estab = None
        vecinos = []
        for c in neighbors(best["combo"]):
            try:
                vecinos.append(evaluate(df, c, start=split))
            except Exception:
                pass
        if vecinos:
            estab = sum(
                1
                for m in vecinos
                if m["ret"] > 0 and m["ops"] >= 4 and m["pf"] > 1.0
            ) / len(vecinos)

        # Un PF gigante con pocas operaciones suele significar "ninguna perdedora"
        # en una muestra chica: no es prueba de robustez, es fragilidad.
        sospechoso = bool(
            best["test"]["pf"] > 20.0 or best["test"]["win"] >= 99.9
        )

        row = {
            "simbolo": sym,
            "split": f"{split:%Y-%m-%d}",
            "default_test_ret": default["ret"],
            "default_test_ops": default["ops"],
            "default_train_ret": default_train["ret"],
            "best_train_ret": best["train"]["ret"],
            "best_test_ret": best["test"]["ret"],
            "best_test_dd": best["test"]["dd"],
            "best_test_pf": best["test"]["pf"],
            "best_test_ops": best["test"]["ops"],
            "best_test_win": best["test"]["win"],
            "mejora_vs_default": mejora,
            "estabilidad": estab if estab is not None else np.nan,
            "es_default": es_default,
            "sospechoso": sospechoso,
            "recomendado": bool(
                not es_default
                and not sospechoso
                and best["test"]["ret"] > 0
                and best["test"]["ops"] >= 6
                and best["test"]["pf"] >= 1.2
                and mejora >= 5.0
                and (estab or 0) >= 0.6
            ),
            "params": (
                "config actual"
                if es_default
                else json.dumps(best["combo"], ensure_ascii=False)
            ),
        }
        rows.append(row)
        print(
            f"{sym:<16} default test {default['ret']:+7.2f}% | "
            f"mejor {'default' if es_default else 'ajustada'} "
            f"{row['best_test_ret']:+.2f}% ({row['best_test_ops']:.0f} ops, "
            f"PF {row['best_test_pf']:.2f}) | estab {row['estabilidad']:.2f} | "
            f"{'RECOMENDADO' if row['recomendado'] else ''} | {time.time() - t0:5.1f}s"
        )

    out = pd.DataFrame(rows).sort_values("best_test_ret", ascending=False)
    out.to_csv(args.out, index=False)
    print(f"\nGuardado en {args.out}")
    print(
        out[
            [
                "simbolo",
                "default_test_ret",
                "best_test_ret",
                "mejora_vs_default",
                "best_test_ops",
                "best_test_dd",
                "best_test_pf",
                "estabilidad",
                "es_default",
                "sospechoso",
                "recomendado",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
