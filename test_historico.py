"""¿Qué exchanges dan más histórico de velas 15m para AAVE?"""

import time

import ccxt
import pandas as pd

SYMBOL = "AAVE/USDT:USDT"
SINCE = int(pd.Timestamp("2019-01-01", tz="UTC").timestamp() * 1000)

candidatos = [
    ("bingx", {"options": {"defaultType": "swap"}}),
    ("binanceusdm", {"options": {"defaultType": "future"}}),
    ("bybit", {"options": {"defaultType": "swap"}}),
    ("okx", {"options": {"defaultType": "swap"}}),
    ("kraken", {"options": {"defaultType": "swap"}}),
]

for name, opts in candidatos:
    ex = getattr(ccxt, name)({"enableRateLimit": True, **opts})
    t0 = time.time()
    try:
        ex.load_markets()
        sym = SYMBOL if SYMBOL in ex.markets else None
        if sym is None:
            sym = next(
                (s for s in ex.markets if s.startswith("AAVE/") and ":" in s),
                None,
            )
        if sym is None:
            print(f"{name:<14} sin mercado AAVE perpetuo")
            continue
        ohlcv = ex.fetch_ohlcv(sym, "15m", since=SINCE, limit=1000)
        if not ohlcv:
            print(f"{name:<14} sin datos ({sym})")
            continue
        first = pd.to_datetime(ohlcv[0][0], unit="ms", utc=True)
        last = pd.to_datetime(ohlcv[-1][0], unit="ms", utc=True)
        print(
            f"{name:<14} {sym:<20} desde {first:%Y-%m-%d %H:%M} "
            f"hasta {last:%Y-%m-%d %H:%M} ({len(ohlcv)} velas, "
            f"{int((time.time()-t0)*1000)} ms)"
        )
    except Exception as exc:
        print(f"{name:<14} ERROR {type(exc).__name__}: {str(exc)[:120]}")
