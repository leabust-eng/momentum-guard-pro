import ccxt

ex = ccxt.bingx({"enableRateLimit": True, "options": {"defaultType": "swap"}})
print("ccxt", ccxt.__version__)
try:
    markets = ex.load_markets()
    print("markets:", len(markets))
    swaps = [s for s, m in markets.items() if m.get("swap") and m.get("linear")]
    print("linear swaps:", len(swaps))
    print("examples:", swaps[:15])
except Exception as e:
    print("load_markets error:", repr(e))

for sym in ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]:
    try:
        ohlcv = ex.fetch_ohlcv(sym, "4h", limit=5)
        print(sym, "->", len(ohlcv), ohlcv[-1] if ohlcv else None)
    except Exception as e:
        print(sym, "ERROR", repr(e))
