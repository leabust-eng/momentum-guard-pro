import ccxt
import pandas as pd

ex = ccxt.bingx({"enableRateLimit": True, "options": {"defaultType": "swap"}})
sym = "BTC/USDT:USDT"

since = int(pd.Timestamp("2026-08-31", tz="UTC").timestamp() * 1000)
for k in range(6):
    rows = ex.fetch_ohlcv(sym, "15m", since=since, limit=1000)
    if not rows:
        print(k, "EMPTY")
        break
    first = pd.to_datetime(rows[0][0], unit="ms", utc=True)
    last = pd.to_datetime(rows[-1][0], unit="ms", utc=True)
    print(k, "n=", len(rows), "first=", first, "last=", last)
    since = rows[-1][0] + 1
