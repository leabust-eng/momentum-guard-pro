"""Compara el backtest con datos de BingX vs el archivo de Binance."""

import io
import urllib.request

import pandas as pd

from engine import Params, load_data, run_backtest

SYM_BINANCE = "AAVEUSDT"
SYM = "AAVE/USDT:USDT"
TF = "15m"
START = pd.Timestamp("2026-07-27")
END = pd.Timestamp("2026-11-04")

BASE = "https://data.binance.vision/data/futures/um"


def _read_zip(url: str) -> pd.DataFrame | None:
    try:
        raw = urllib.request.urlopen(url, timeout=60).read()
    except Exception:
        return None
    df = pd.read_csv(io.BytesIO(raw), compression="zip", header=None)
    if not len(df):
        return None
    df = df.iloc[:, :6]
    df.columns = ["ts", "Open", "High", "Low", "Close", "Volume"]
    # Algunos archivos traen fila de encabezado.
    df = df[pd.to_numeric(df["ts"], errors="coerce").notna()]
    for col in ("Open", "High", "Low", "Close", "Volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["Open", "High", "Low", "Close"])


def binance_archive(sym: str, tf: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    frames = []
    for ym in pd.period_range(start.to_period("M"), end.to_period("M"), freq="M"):
        name = ym.strftime("%Y-%m")
        url = f"{BASE}/monthly/klines/{sym}/{tf}/{sym}-{tf}-{name}.zip"
        df = _read_zip(url)
        if df is not None:
            frames.append(df)
            continue
        # mes en curso: bajar día por día
        for day in pd.date_range(ym.start_time, ym.end_time.normalize(), freq="D"):
            d = day.strftime("%Y-%m-%d")
            url = f"{BASE}/daily/klines/{sym}/{tf}/{sym}-{tf}-{d}.zip"
            part = _read_zip(url)
            if part is not None:
                frames.append(part)
    out = pd.concat(frames, ignore_index=True).drop_duplicates("ts")
    out["ts"] = pd.to_numeric(out["ts"], errors="coerce").astype("int64")
    out["ts"] = pd.to_datetime(out["ts"], unit="ms", utc=True).dt.tz_localize(None)
    out = out.set_index("ts").sort_index()
    return out[(out.index >= start) & (out.index < end + pd.Timedelta(days=1))]


p = Params()
print("descargando Binance...")
bn = binance_archive(SYM_BINANCE, TF, START - pd.Timedelta(days=30), END)
print(f"Binance: {len(bn):,} velas | {bn.index.min()} -> {bn.index.max()}")

print("descargando BingX...")
bx = load_data("bingx", SYM, TF, str((START - pd.Timedelta(days=30)).date()), str(END.date()))
print(f"BingX:   {len(bx):,} velas | {bx.index.min()} -> {bx.index.max()}")

r_bx = run_backtest(bx, p, trade_start=START)
r_bn = run_backtest(bn, p, trade_start=START)

for name, r in (("BINGX", r_bx), ("BINANCE", r_bn)):
    m = r.metrics
    print(
        f"\n{name}: ret {m['total_return']*100:+.2f}% | ops {m['n_trades']} | "
        f"aciertos {m['win_rate']*100:.1f}% | DD {m['max_dd']*100:.2f}% | "
        f"PF {m['profit_factor']:.2f}"
    )

print("\noperaciones (entrada / salida / pnl):")
tr_bx = r_bx.trades
tr_bn = r_bn.trades
n = max(len(tr_bx), len(tr_bn))
for i in range(n):
    a = tr_bx.iloc[i] if i < len(tr_bx) else None
    b = tr_bn.iloc[i] if i < len(tr_bn) else None
    fmt = lambda t: (
        f"{t['entry_time']:%m-%d %H:%M}->{t['exit_time']:%m-%d %H:%M} "
        f"{t['entry_price']:8.2f}/{t['exit_price']:8.2f} {t['pnl']:+9.2f}"
        if t is not None
        else "—"
    )
    print(f"{i:>2}  {fmt(a):<52} | {fmt(b)}")
