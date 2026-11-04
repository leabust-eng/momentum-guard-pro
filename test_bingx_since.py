import ccxt
import pandas as pd

ex = ccxt.bingx({"enableRateLimit": True, "options": {"defaultType": "swap"}})
sym = "BTC/USDT:USDT"

def ms(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp() * 1000)

for start in ["2022-01-01", "2023-01-01", "2024-01-01", "2025-01-01", "2026-01-01", "2026-08-01"]:
    try:
        rows = ex.fetch_ohlcv(sym, "4h", since=ms(start), limit=5)
        if rows:
            first = pd.to_datetime(rows[0][0], unit="ms", utc=True)
            last = pd.to_datetime(rows[-1][0], unit="ms", utc=True)
            print(start, "->", len(rows), first, "to", last)
        else:
            print(start, "-> EMPTY")
    except Exception as e:
        print(start, "ERROR", repr(e))

print("--- latest 5 ---")
rows = ex.fetch_ohlcv(sym, "4h", limit=5)
for r in rows:
    print(pd.to_datetime(r[0], unit="ms", utc=True), r[1:])
