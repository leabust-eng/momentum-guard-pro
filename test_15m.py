from engine import Params, load_data, run_backtest

df = load_data("bingx", "BTC/USDT:USDT", "15m", "2026-08-31", "2026-11-01")
print("bars:", len(df), "from", df.index.min(), "to", df.index.max())
print(df.head(2))
print(df.tail(2))

res = run_backtest(df, Params())
print("--- metrics ---")
for k, v in res.metrics.items():
    print(f"{k:>18}: {v}")
if len(res.trades):
    print("--- trades ---")
    print(res.trades.to_string())
