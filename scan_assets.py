import warnings

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

tickers = [
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD",
    "DOGE-USD", "AVAX-USD", "LINK-USD", "DOT-USD", "LTC-USD", "BCH-USD",
    "TRX-USD", "ATOM-USD", "NEAR-USD", "APT-USD", "ARB-USD", "OP-USD",
    "INJ-USD", "SUI-USD", "SEI-USD", "TIA-USD", "PEPE-USD", "SHIB-USD",
    "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META", "AMD",
    "NFLX", "COIN", "MSTR", "PLTR", "SPY", "QQQ", "IWM", "GLD", "SLV",
    "TLT", "ARKK",
]

rows = []
for t in tickers:
    try:
        df = yf.download(t, start="2026-08-31", end="2026-11-02", progress=False, auto_adjust=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if len(df) < 10:
            continue
        c = df["Close"].dropna()
        c0 = float(c.iloc[0])
        c1 = float(c.iloc[-1])
        peak = float(c.max())
        trough_after_peak = float(c.loc[c.idxmax():].min())
        end_ret = 100 * (c1 / c0 - 1)
        peak_ret = 100 * (peak / c0 - 1)
        dd = 100 * (trough_after_peak / peak - 1)
        rows.append((t, end_ret, peak_ret, dd))
    except Exception:
        pass

rows.sort(key=lambda r: abs(r[1] - 16.07))
print(f"{'Ticker':10s} {'EndRet':>9s} {'PeakRet':>9s} {'DDfromPeak':>11s}")
for t, er, pr, dd in rows[:20]:
    print(f"{t:10s} {er:+8.2f}% {pr:+8.2f}% {dd:+10.2f}%")
