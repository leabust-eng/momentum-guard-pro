"""Validación walk-forward de los presets ajustados.

Toma cada símbolo recomendado por `optimize_symbols.py` y lo parte en 3 bloques
temporales iguales. Un preset robusto debería ganar en la mayoría de los bloques,
no solo en el tercio que se usó para validar.

También corre la configuración actual en los mismos bloques como referencia.
"""

import json
from dataclasses import replace

import pandas as pd

from engine import Params, find_earliest_bingx, load_data, run_backtest

BASE = Params(
    initial_capital=3000.0,
    leverage=3.0,
    position_pct=0.9,
    commission=0.0005,
    slippage=0.0002,
    funding_rate_8h=0.0001,
    maintenance_margin=0.005,
)

DEFAULT = {
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


def build(combo: dict) -> Params:
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


def block_stats(df, params, start, end=None) -> tuple[int, float, float]:
    part = df[(df.index >= start) & (df.index < end)] if end is not None else df[df.index >= start]
    if len(part) < 50:
        return 0, 0.0, 0.0
    res = run_backtest(part, params)
    m = res.metrics
    return int(m["n_trades"]), float(m["total_return"] * 100.0), float(m["profit_factor"])


def main() -> None:
    opt = pd.read_csv("optimizer_results.csv")
    rec = opt[opt["recomendado"]].sort_values("best_test_ret", ascending=False)

    rows = []
    for _, r in rec.iterrows():
        sym = r["simbolo"]
        combo = json.loads(r["params"])
        combo["ema_band"] = tuple(combo["ema_band"])
        tuned = build(combo)

        earliest = find_earliest_bingx(sym, "15m")
        df = load_data("bingx", sym, "15m", str(earliest.date()), "2026-11-06")
        idx = df.index
        cuts = [idx[0], idx[len(idx) // 3], idx[2 * len(idx) // 3], idx[-1] + pd.Timedelta(minutes=15)]

        print(f"\n{sym}  ({idx[0]:%Y-%m-%d} -> {idx[-1]:%Y-%m-%d})")
        for name, params in (("actual", build(DEFAULT)), ("ajustada", tuned)):
            line = []
            for k in range(3):
                ops, ret, pf = block_stats(df, params, cuts[k], cuts[k + 1])
                line.append(f"B{k + 1}: {ret:+7.2f}% ({ops:>2} ops, PF {pf:4.2f})")
            o, rt, pf = block_stats(df, params, cuts[0])
            positivos = sum(
                1
                for k in range(3)
                if block_stats(df, params, cuts[k], cuts[k + 1])[1] > 0
                and block_stats(df, params, cuts[k], cuts[k + 1])[0] >= 2
            )
            print(f"  {name:<9} {' | '.join(line)} | total {rt:+7.2f}% ({o} ops) | bloques ganadores {positivos}/3")
            if name == "ajustada":
                rows.append(
                    {
                        "simbolo": sym,
                        "bloques_ganadores": positivos,
                        "total_ret": rt,
                        "total_ops": o,
                        "total_pf": pf,
                    }
                )

    out = pd.DataFrame(rows).sort_values(["bloques_ganadores", "total_ret"], ascending=False)
    out.to_csv("walkforward_presets.csv", index=False)
    print("\n=== RESUMEN ===")
    print(out.to_string(index=False))
    print("\nGuardado en walkforward_presets.csv")


if __name__ == "__main__":
    main()
