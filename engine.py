"""Motor de backtest para Momentum Guard Pro.

Soporta:
- Datos de futuros perpetuos de BingX vía ccxt.
- Datos de Yahoo Finance (spot/acciones) como alternativa.
- Leverage, margen, funding y liquidación aproximada.
- Todos los parámetros de la estrategia original de Pine v6.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import ccxt
import numpy as np
import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# Caché en disco (evita volver a descargar tras reiniciar la app)
# ---------------------------------------------------------------------------
_CACHE_DIR = Path(__file__).with_name(".cache")
_DATA_DIR = Path(__file__).with_name("data")
_ARCHIVE_DIR = _DATA_DIR / "archivo"
_SNAPSHOT_DIR = _DATA_DIR / "snapshot"
_EARLIEST_TTL_S = 12 * 3600


def _cache_file(name: str) -> Path:
    _CACHE_DIR.mkdir(exist_ok=True)
    return _CACHE_DIR / name


def _is_fresh(path: Path, ttl_s: float) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) < ttl_s


def _index_path() -> Path:
    return _CACHE_DIR / "index.json"


def _load_index() -> dict:
    try:
        return json.loads(_index_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_index(index: dict) -> None:
    try:
        _index_path().write_text(json.dumps(index), encoding="utf-8")
    except OSError:
        pass


def clear_cache() -> None:
    """Borra la caché local de datos y de fecha de inicio."""
    if not _CACHE_DIR.exists():
        return
    for path in _CACHE_DIR.glob("*"):
        try:
            path.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Archivo permanente de velas BingX
# ---------------------------------------------------------------------------
# BingX conserva pocos días de velas y las va borrando. Para poder backtestear
# más adelante, cada descarga se acumula en data/archivo/. Un snapshot de ese
# archivo se commitea en data/snapshot/ para que la app en la nube también lo
# tenga. El archivo vivo está fuera de .cache, así "Actualizar datos" no lo borra.
def _safe_symbol(symbol: str) -> str:
    base = symbol.split(":")[0]
    return re.sub(r"[^A-Z0-9]", "", base.upper())


def _archive_path(symbol: str, timeframe: str) -> Path:
    _ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    return _ARCHIVE_DIR / f"bingx_{_safe_symbol(symbol)}_{timeframe}.parquet"


def _snapshot_path(symbol: str, timeframe: str) -> Path:
    return _SNAPSHOT_DIR / f"bingx_{_safe_symbol(symbol)}_{timeframe}.parquet"


def _read_saved_bars(path: Path) -> pd.DataFrame | None:
    try:
        if path.exists():
            df = pd.read_parquet(path)
            if len(df):
                return df
    except Exception:
        pass
    return None


def load_archived_bars(symbol: str, timeframe: str) -> pd.DataFrame:
    """Velas BingX guardadas: snapshot del repo + archivo vivo."""
    frames = [
        df
        for path in (_snapshot_path(symbol, timeframe), _archive_path(symbol, timeframe))
        if (df := _read_saved_bars(path)) is not None
    ]
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames)
    return out[~out.index.duplicated(keep="last")].sort_index()


def archive_earliest(symbol: str, timeframe: str) -> pd.Timestamp | None:
    df = load_archived_bars(symbol, timeframe)
    return None if df.empty else df.index.min()


def _update_archive(symbol: str, timeframe: str, df: pd.DataFrame) -> None:
    if df.empty:
        return
    path = _archive_path(symbol, timeframe)
    old = _read_saved_bars(path)
    if old is not None:
        df = pd.concat([old, df])
    df = df[~df.index.duplicated(keep="last")].sort_index()
    try:
        df.to_parquet(path)
    except Exception:
        pass


def _with_archive(
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> pd.DataFrame:
    hist = load_archived_bars(symbol, timeframe)
    if hist.empty or df.empty:
        return df
    hist = hist[(hist.index >= start_ts) & (hist.index < end_ts)]
    if hist.empty:
        return df
    out = pd.concat([hist, df])
    return out[~out.index.duplicated(keep="last")].sort_index()


def snapshot_archive() -> list[dict[str, object]]:
    """Copia el archivo vivo a data/snapshot/ para commitearlo al repo."""
    _SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    resumen: list[dict[str, object]] = []
    for path in sorted(_ARCHIVE_DIR.glob("*.parquet")):
        live = _read_saved_bars(path)
        if live is None:
            continue
        target = _SNAPSHOT_DIR / path.name
        old = _read_saved_bars(target)
        merged = live if old is None else pd.concat([old, live])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
        merged.to_parquet(target)
        resumen.append(
            {
                "archivo": path.name,
                "velas": len(merged),
                "desde": merged.index.min(),
                "hasta": merged.index.max(),
            }
        )
    return resumen


def find_earliest_bingx(symbol: str, timeframe: str, max_age_s: float = _EARLIEST_TTL_S) -> pd.Timestamp:
    """Inicio más antiguo entre lo que conserva BingX y el archivo propio."""
    earliest = find_earliest_available(symbol, timeframe, max_age_s)
    archived = archive_earliest(symbol, timeframe)
    if archived is not None and archived < earliest:
        return archived
    return earliest


# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------
@dataclass
class Params:
    # 1. CUSUM
    cusum_vol_period: int = 30
    cusum_drift: float = 0.5
    cusum_threshold: float = 5.0
    pending_bars: int = 1

    # 2. Confirmación de mercado
    use_ema: bool = True
    ema_len: int = 200
    ema_slope_bars: int = 1
    require_2bars: bool = False
    require_color: bool = True
    use_ema_dist: bool = True
    min_ema_dist_pct: float = 1.0
    max_ema_dist_pct: float = 1.6

    use_rsi: bool = True
    rsi_len: int = 14
    rsi_ob: float = 75.0
    rsi_os: float = 20.0

    use_chop: bool = True
    chop_len: int = 14
    chop_max: float = 50.0

    # 3. ZLEMA
    use_zlag: bool = True
    zlag_len: int = 70
    zlag_mult: float = 2.2

    # 4. Riesgo
    trade_dir: str = "Ambos"  # "Ambos" | "Solo Long" | "Solo Short"
    one_way: bool = True
    sl_pct: float = 0.04
    use_ts: bool = True
    ts_act_pct: float = 0.02
    ts_atr_len: int = 14
    ts_atr_mult: float = 6.0

    # Futuros
    leverage: float = 1.0
    position_pct: float = 1.0
    maintenance_margin: float = 0.005
    apply_funding: bool = True
    funding_rate_8h: float = 0.0001

    # Ejecución
    initial_capital: float = 10_000.0
    commission: float = 0.0005
    slippage: float = 0.0002
    exec_mode: str = "close"  # "close" | "next_open"


@dataclass
class BacktestResult:
    equity: pd.Series
    buy_hold: pd.Series
    trades: pd.DataFrame
    metrics: dict
    signals: pd.DataFrame
    params: Params


# ---------------------------------------------------------------------------
# Indicadores
# ---------------------------------------------------------------------------
def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _rma(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1.0 / n, adjust=False).mean()


def _true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["Close"].shift(1)
    return pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    return _rma(_true_range(df), n)


def _rsi(close: pd.Series, n: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = _rma(gain, n)
    avg_loss = _rma(loss, n)
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    out = out.mask((avg_loss == 0.0) & (avg_gain > 0.0), 100.0)
    out = out.mask((avg_gain == 0.0) & (avg_loss > 0.0), 0.0)
    out = out.mask((avg_gain == 0.0) & (avg_loss == 0.0), 50.0)
    return out


def _chop(df: pd.DataFrame, n: int) -> pd.Series:
    tr = _true_range(df)
    ci_sum = tr.rolling(n).sum()
    ci_range = (df["High"].rolling(n).max() - df["Low"].rolling(n).min()).clip(lower=1e-12)
    return 100.0 * np.log10(ci_sum / ci_range) / np.log10(n)


def _cusum(df: pd.DataFrame, p: Params) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    close = df["Close"].to_numpy(float)
    diff = np.full(len(close), np.nan)
    diff[1:] = np.diff(close)
    vol = pd.Series(diff).rolling(p.cusum_vol_period).std(ddof=0).to_numpy(float)
    vol_adj = np.where(np.isnan(vol) | (vol == 0.0), 1e-8, vol)

    n = len(close)
    baseline = close[0]
    s_pos = 0.0
    s_neg = 0.0
    pending_dir = 0
    pending_age = 0
    event_up = np.zeros(n, dtype=bool)
    event_dn = np.zeros(n, dtype=bool)
    pending = np.zeros(n, dtype=int)

    for i in range(n):
        if i > 0 and not np.isnan(vol[i]):
            dev_up = (close[i] - baseline) / vol_adj[i]
            dev_down = (baseline - close[i]) / vol_adj[i]
            new_pos = max(0.0, s_pos + dev_up - p.cusum_drift)
            new_neg = max(0.0, s_neg + dev_down - p.cusum_drift)

            up = False
            dn = False
            if new_pos > p.cusum_threshold:
                baseline = close[i]
                s_pos = 0.0
                s_neg = 0.0
                up = True
            elif new_neg > p.cusum_threshold:
                baseline = close[i]
                s_pos = 0.0
                s_neg = 0.0
                dn = True
            else:
                s_pos = new_pos
                s_neg = new_neg

            event_up[i] = up
            event_dn[i] = dn

            if up:
                pending_dir = 1
                pending_age = 0
            elif dn:
                pending_dir = -1
                pending_age = 0
            elif pending_dir != 0:
                pending_age += 1
                if pending_age > p.pending_bars:
                    pending_dir = 0
                    pending_age = 0

        pending[i] = pending_dir

    return event_up, event_dn, pending


def _ztrend(close: np.ndarray, zlema: np.ndarray, zvol: np.ndarray) -> np.ndarray:
    n = len(close)
    z = np.zeros(n, dtype=int)
    trend = 0
    for i in range(1, n):
        if (
            np.isnan(zlema[i])
            or np.isnan(zvol[i])
            or np.isnan(zlema[i - 1])
            or np.isnan(zvol[i - 1])
        ):
            z[i] = trend
            continue
        upper = zlema[i] + zvol[i]
        lower = zlema[i] - zvol[i]
        prev_upper = zlema[i - 1] + zvol[i - 1]
        prev_lower = zlema[i - 1] - zvol[i - 1]
        if close[i - 1] <= prev_upper and close[i] > upper:
            trend = 1
        if close[i - 1] >= prev_lower and close[i] < lower:
            trend = -1
        z[i] = trend
    return z


# ---------------------------------------------------------------------------
# Datos: BingX
# ---------------------------------------------------------------------------
def normalize_bingx_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if not s:
        return "BTC/USDT:USDT"
    if s.endswith(":USDT"):
        return s
    s = s.replace("-", "/").replace("_", "/")
    if "/" not in s:
        base = s[:-4] if s.endswith("USDT") else s
        s = f"{base}/USDT"
    if not s.endswith(":USDT"):
        s = f"{s}:USDT"
    return s


def _to_ms(ts) -> int:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return int(t.timestamp() * 1000)


def _is_retryable(exc: Exception) -> bool:
    """Errores de red o límites de tasa que conviene reintentar."""
    if isinstance(
        exc,
        (
            ccxt.NetworkError,
            ccxt.RequestTimeout,
            ccxt.ExchangeNotAvailable,
            ccxt.DDoSProtection,
            ccxt.RateLimitExceeded if hasattr(ccxt, "RateLimitExceeded") else ccxt.NetworkError,
        ),
    ):
        return True
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "100410",
            "rate",
            "retry",
            "429",
            "timeout",
            "timed out",
            "connection",
            "temporarily",
            "unavailable",
            "econnreset",
            "econnrefused",
            "getaddrinfo",
            "ssl",
        )
    )


def _sleep_before_retry(attempt: int) -> None:
    time.sleep(min(2**attempt, 30))


def _load_markets(ex: ccxt.Exchange, max_retries: int = 6):
    last_exc = None
    for attempt in range(max_retries):
        try:
            return ex.load_markets()
        except Exception as exc:
            last_exc = exc
            if _is_retryable(exc):
                _sleep_before_retry(attempt)
            else:
                raise
    raise ConnectionError(
        "BingX no respondió al listar los mercados. Revisá tu conexión y "
        "volvé a intentar en unos segundos."
    ) from last_exc


def _fetch_with_retry(
    ex: ccxt.Exchange,
    sym: str,
    timeframe: str,
    since: int,
    limit: int = 1000,
    max_retries: int = 6,
):
    last_exc = None
    for attempt in range(max_retries):
        try:
            return ex.fetch_ohlcv(sym, timeframe, since=since, limit=limit)
        except Exception as exc:
            last_exc = exc
            if _is_retryable(exc):
                _sleep_before_retry(attempt)
            else:
                raise
    raise ConnectionError(
        "BingX no respondió tras varios intentos (red o rate limit). "
        "Esperá 30-60 segundos y volvé a intentar."
    ) from last_exc


# ---------------------------------------------------------------------------
# Precio en vivo (para el panel de riesgo)
# ---------------------------------------------------------------------------
_LIVE_LOCK = threading.Lock()
_LIVE_EX: ccxt.Exchange | None = None
_LIVE_MARKETS_READY = False


def _live_exchange() -> ccxt.Exchange:
    """Reutiliza una sola conexión a BingX: listar mercados tarda ~5 s."""
    global _LIVE_EX, _LIVE_MARKETS_READY
    with _LIVE_LOCK:
        if _LIVE_EX is None:
            _LIVE_EX = ccxt.bingx(
                {"enableRateLimit": True, "options": {"defaultType": "swap"}}
            )
        if not _LIVE_MARKETS_READY:
            _load_markets(_LIVE_EX, max_retries=3)
            _LIVE_MARKETS_READY = True
        return _LIVE_EX


def fetch_live_price(symbol: str, max_retries: int = 3) -> float:
    """Último precio operado en BingX (ej. AAVE/USDT:USDT)."""
    sym = normalize_bingx_symbol(symbol)
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            ex = _live_exchange()
            ticker = ex.fetch_ticker(sym)
            last = ticker.get("last")
            if last is None:
                info = ticker.get("info") or {}
                last = info.get("lastPrice") or info.get("last") or info.get("price")
            if last is None:
                raise ValueError(f"BingX no devolvió precio para {sym}.")
            return float(last)
        except Exception as exc:
            last_exc = exc
            if _is_retryable(exc):
                _sleep_before_retry(attempt)
            else:
                raise
    raise ConnectionError(
        "BingX no respondió al pedir el precio en vivo. "
        "Se muestra el último cierre de la vela."
    ) from last_exc


def _timeframe_ms(timeframe: str) -> int:
    return int(pd.Timedelta(timeframe).total_seconds() * 1000)


def find_earliest_available(
    symbol: str, timeframe: str, max_age_s: float = _EARLIEST_TTL_S
) -> pd.Timestamp:
    """Devuelve la fecha de la vela más antigua que BingX conserva.

    BingX no mantiene todo el histórico en todos los timeframes (por ejemplo,
    en 15m suele conservar ~100 días). Se localiza con búsqueda binaria por
    días y luego se pide el primer bloque de velas para afinar la fecha.
    El resultado se cachea en disco: la búsqueda hace ~12 peticiones y BingX
    limita la tasa, así que repetirla en cada reinicio es caro.
    """
    key = hashlib.md5(f"earliest|{symbol}|{timeframe}|v1".encode()).hexdigest()[:16]
    path = _cache_file(f"earliest_{key}.json")
    if _is_fresh(path, max_age_s):
        try:
            return pd.Timestamp(json.loads(path.read_text(encoding="utf-8"))["ts"])
        except Exception:
            pass

    ts = _query_earliest(symbol, timeframe)
    try:
        path.write_text(
            json.dumps({"ts": ts.isoformat(), "symbol": symbol, "timeframe": timeframe}),
            encoding="utf-8",
        )
    except OSError:
        pass
    return ts


def _query_earliest(symbol: str, timeframe: str) -> pd.Timestamp:
    ex = ccxt.bingx({"enableRateLimit": True, "options": {"defaultType": "swap"}})
    sym = normalize_bingx_symbol(symbol)
    markets = _load_markets(ex)
    if sym not in markets:
        raise ValueError(f"Símbolo {sym} no encontrado en BingX.")

    step = _timeframe_ms(timeframe)
    day = 24 * 60 * 60 * 1000
    lo = _to_ms("2015-01-01")
    hi = _to_ms(pd.Timestamp.now("UTC"))

    def has_data(t: int) -> bool:
        batch = _fetch_with_retry(ex, sym, timeframe, t, limit=2)
        return bool(batch) and batch[0][0] <= t + step

    while hi - lo > day:
        mid = (lo + hi) // 2
        mid -= mid % day
        if mid <= lo:
            mid = lo + day
        if has_data(mid):
            hi = mid
        else:
            lo = mid

    batch = _fetch_with_retry(ex, sym, timeframe, hi - day, limit=1000)
    if not batch:
        batch = _fetch_with_retry(ex, sym, timeframe, hi, limit=1000)
    if not batch:
        raise ValueError(f"BingX no tiene histórico para {sym} en {timeframe}.")
    return pd.to_datetime(batch[0][0], unit="ms", utc=True).tz_localize(None)


def load_bingx_data(symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
    ex = ccxt.bingx({"enableRateLimit": True, "options": {"defaultType": "swap"}})
    sym = normalize_bingx_symbol(symbol)
    markets = _load_markets(ex)
    if sym not in markets:
        base = sym.split("/")[0]
        candidates = [s for s in markets if s.upper().startswith(base + "/") and markets[s].get("swap")]
        raise ValueError(
            f"Símbolo {sym} no encontrado en BingX. "
            f"Ejemplos disponibles: {', '.join(candidates[:8])}"
        )

    since = _to_ms(start)
    end_ms = _to_ms(pd.Timestamp(end) + pd.Timedelta(days=1))

    # Algunos símbolos no tienen histórico desde la fecha pedida.
    # Si BingX ya borró esas velas, saltamos al inicio que todavía conserva.
    batch = _fetch_with_retry(ex, sym, timeframe, since)
    if not batch:
        earliest = find_earliest_available(symbol, timeframe)
        since = max(since, _to_ms(earliest))
        batch = _fetch_with_retry(ex, sym, timeframe, since)

    if not batch:
        raise ValueError(f"BingX no devolvió datos para {sym} en el rango solicitado.")

    rows: list[list] = []
    while batch:
        rows.extend(batch)
        last = batch[-1][0]
        if last <= since or last >= end_ms:
            break
        since = last + 1
        time.sleep(0.25)
        batch = _fetch_with_retry(ex, sym, timeframe, since)

    if not rows:
        raise ValueError(f"BingX no devolvió datos para {sym} en el rango solicitado.")

    df = pd.DataFrame(rows, columns=["ts", "Open", "High", "Low", "Close", "Volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.tz_localize(None)
    df = df.drop_duplicates("ts").set_index("ts").sort_index()
    df = df[(df.index >= pd.Timestamp(start)) & (df.index < pd.Timestamp(end) + pd.Timedelta(days=1))]
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    if len(df) == 0:
        raise ValueError(f"BingX no devolvió datos para {sym} en el rango solicitado.")
    return df


# ---------------------------------------------------------------------------
# Datos: Yahoo Finance (alternativa)
# ---------------------------------------------------------------------------
_CRYPTO_BASES = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "LINK", "DOT",
    "LTC", "BCH", "TRX", "ATOM", "NEAR", "APT", "ARB", "OP", "INJ", "SUI",
    "SEI", "TIA", "PEPE", "SHIB", "MATIC", "UNI", "AAVE",
}


def normalize_yahoo_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if not s:
        return "BTC-USD"
    if s.endswith("USDT"):
        return f"{s[:-4]}-USD"
    if "-" in s or "=" in s:
        return s
    if s in _CRYPTO_BASES:
        return f"{s}-USD"
    return s


def load_yahoo_data(symbol: str, interval: str, start: str, end: str) -> pd.DataFrame:
    sym = normalize_yahoo_symbol(symbol)
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1)

    if interval == "1d":
        raw = yf.download(sym, start=start_ts, end=end_ts, interval="1d", progress=False, auto_adjust=False)
    elif interval in ("15m", "30m"):
        raw = yf.download(sym, start=start_ts, end=end_ts, interval=interval, progress=False, auto_adjust=False)
    else:
        # 1h, 2h, 4h, 6h, 12h -> descargar 1h y remuestrear
        max_start = pd.Timestamp.today().normalize() - pd.Timedelta(days=729)
        if start_ts < max_start:
            start_ts = max_start
        raw = yf.download(sym, start=start_ts, end=end_ts, interval="1h", progress=False, auto_adjust=False)

    if raw is None or len(raw) == 0:
        raise ValueError(f"No hay datos para {sym} en el rango solicitado.")

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in raw.columns]
    df = raw[cols].copy()
    if "Volume" not in df.columns:
        df["Volume"] = 0.0
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    df = df[~df.index.duplicated(keep="last")].sort_index()

    if interval in ("2h", "4h", "6h", "12h"):
        df = (
            df.resample(interval)
            .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
            .dropna(subset=["Open", "High", "Low", "Close"])
        )

    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)

    return df


def load_data(
    source: str,
    symbol: str,
    interval: str,
    start: str,
    end: str,
    max_age_s: float | None = None,
) -> pd.DataFrame:
    """Descarga OHLCV, con caché en disco por combinación de parámetros.

    Si ya hay una descarga cacheada que cubre el rango pedido (por ejemplo el
    histórico completo cuando se pide "últimos 30 días"), se reutiliza y se
    recorta: así cambiar de ventana no vuelve a pedir velas a BingX.

    Los rangos que terminan hoy (o en el futuro) se refrescan cada 15 minutos;
    los rangos ya cerrados se guardan 7 días.
    """
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1)
    is_bingx = source.lower().startswith("bingx")
    src = "bingx" if is_bingx else "yahoo"

    if max_age_s is None:
        today = pd.Timestamp.now("UTC").tz_localize(None).normalize()
        max_age_s = 900 if end_ts >= today else 7 * 86400

    key = hashlib.md5(
        f"ohlcv|{src}|{symbol}|{interval}|{start}|{end}|v1".encode()
    ).hexdigest()[:16]
    path = _cache_file(f"ohlcv_{key}.parquet")

    if _is_fresh(path, max_age_s):
        try:
            cached = pd.read_parquet(path)
            if len(cached):
                if is_bingx:
                    _update_archive(symbol, interval, cached)
                    return _with_archive(symbol, interval, cached, start_ts, end_ts)
                return cached
        except Exception:
            pass

    # ¿Alguna descarga cacheada que cubra [start, end)?
    index = _load_index()
    for meta in index.values():
        if (
            meta.get("source") != src
            or meta.get("symbol") != symbol
            or meta.get("interval") != interval
        ):
            continue
        if pd.Timestamp(meta["start"]) > start_ts:
            continue
        if pd.Timestamp(meta["end"]) + pd.Timedelta(days=1) < end_ts:
            continue
        other = _CACHE_DIR / meta.get("file", "")
        if not _is_fresh(other, max_age_s):
            continue
        try:
            wide = pd.read_parquet(other)
        except Exception:
            continue
        subset = wide[(wide.index >= start_ts) & (wide.index < end_ts)]
        if len(subset):
            if is_bingx:
                _update_archive(symbol, interval, subset)
                return _with_archive(symbol, interval, subset, start_ts, end_ts)
            return subset

    if is_bingx:
        df = load_bingx_data(symbol, interval, start, end)
        _update_archive(symbol, interval, df)
        df = _with_archive(symbol, interval, df, start_ts, end_ts)
    else:
        df = load_yahoo_data(symbol, interval, start, end)

    file_name = path.name
    try:
        df.to_parquet(path)
        index[key] = {
            "source": src,
            "symbol": symbol,
            "interval": interval,
            "start": str(pd.Timestamp(start).date()),
            "end": str(pd.Timestamp(end).date()),
            "file": file_name,
        }
        _save_index(index)
    except Exception:
        pass
    return df


# ---------------------------------------------------------------------------
# Backtest (modelo de futuros con equity)
# ---------------------------------------------------------------------------
class _State:
    def __init__(self, p: Params) -> None:
        self.equity = p.initial_capital
        self.position = 0
        self.units = 0.0
        self.entry_price = 0.0
        self.entry_time = None
        self.entry_bar = -1
        self.entry_equity = p.initial_capital
        self.notional = 0.0
        self.margin = 0.0
        self.liq_price = np.nan
        self.stop_level = np.nan
        self.highest_price = np.nan
        self.lowest_price = np.nan
        self.ts_active = False
        self.funding_paid = 0.0
        self.trades: list[dict] = []


def _enter(state: _State, direction: int, i: int, raw_price: float, df: pd.DataFrame, p: Params) -> None:
    fill = raw_price * (1.0 + direction * p.slippage)
    notional = state.equity * p.position_pct * p.leverage
    if notional <= 0:
        return
    units = notional / fill
    commission = notional * p.commission

    state.entry_equity = state.equity
    state.equity -= commission

    state.position = direction
    state.units = units
    state.entry_price = fill
    state.entry_time = df.index[i]
    state.entry_bar = i
    state.notional = notional
    state.margin = notional / p.leverage
    state.liq_price = (
        fill * (1.0 - 1.0 / p.leverage + p.maintenance_margin)
        if direction == 1
        else fill * (1.0 + 1.0 / p.leverage - p.maintenance_margin)
    )
    state.stop_level = fill * (1.0 - direction * p.sl_pct)
    state.highest_price = float(df["High"].iloc[i]) if direction == 1 else np.nan
    state.lowest_price = float(df["Low"].iloc[i]) if direction == -1 else np.nan
    state.ts_active = False
    state.funding_paid = 0.0


def _exit(state: _State, i: int, raw_price: float, reason: str, df: pd.DataFrame, p: Params) -> None:
    direction = state.position
    fill = raw_price * (1.0 - direction * p.slippage)
    pnl = direction * state.units * (fill - state.entry_price)
    exit_commission = state.units * fill * p.commission
    state.equity += pnl - exit_commission
    if reason == "liquidation":
        state.equity = max(0.0, state.equity)

    pnl_total = state.equity - state.entry_equity
    ret = pnl_total / state.entry_equity * 100.0 if state.entry_equity else 0.0
    state.trades.append(
        {
            "entry_time": state.entry_time,
            "exit_time": df.index[i],
            "direction": "Long" if direction == 1 else "Short",
            "entry_price": state.entry_price,
            "exit_price": fill,
            "units": state.units,
            "notional": state.notional,
            "margin": state.margin,
            "leverage": p.leverage,
            "pnl": pnl_total,
            "return_pct": ret,
            "funding_paid": state.funding_paid,
            "bars_held": i - state.entry_bar,
            "exit_reason": reason,
        }
    )

    state.position = 0
    state.units = 0.0
    state.entry_price = 0.0
    state.entry_time = None
    state.entry_bar = -1
    state.notional = 0.0
    state.margin = 0.0
    state.liq_price = np.nan
    state.stop_level = np.nan
    state.highest_price = np.nan
    state.lowest_price = np.nan
    state.ts_active = False
    state.funding_paid = 0.0


def run_backtest(
    df: pd.DataFrame,
    p: Params,
    trade_start: pd.Timestamp | str | None = None,
) -> BacktestResult:
    close = df["Close"]
    open_ = df["Open"]
    high = df["High"]
    low = df["Low"]

    o = open_.to_numpy(float)
    h = high.to_numpy(float)
    l = low.to_numpy(float)
    c = close.to_numpy(float)

    n = len(df)
    i0 = 0
    if trade_start is not None:
        ts = pd.Timestamp(trade_start)
        idx = df.index
        if getattr(idx, "tz", None) is not None:
            if ts.tzinfo is None:
                ts = ts.tz_localize(idx.tz)
            else:
                ts = ts.tz_convert(idx.tz)
        elif ts.tzinfo is not None:
            ts = ts.tz_convert(None)
        i0 = int(idx.searchsorted(ts, side="left"))
        i0 = min(max(i0, 0), n - 1)

    # Indicadores
    ema_val = _ema(close, p.ema_len)
    ema_up = ema_val > ema_val.shift(p.ema_slope_bars)
    ema_dn = ema_val < ema_val.shift(p.ema_slope_bars)
    rsi_val = _rsi(close, p.rsi_len)
    chop_val = _chop(df, p.chop_len)
    atr_ts = _atr(df, p.ts_atr_len)

    zlag_lag = int(np.floor((p.zlag_len - 1) / 2))
    zlema = _ema(close + (close - close.shift(zlag_lag)), p.zlag_len)
    zvol = _atr(df, p.zlag_len).rolling(p.zlag_len * 3).max() * p.zlag_mult
    zt = _ztrend(c, zlema.to_numpy(float), zvol.to_numpy(float))

    event_up, event_dn, pending = _cusum(df, p)

    # Condiciones vectorizadas
    verde_act = close > open_
    verde_prev = close.shift(1) > open_.shift(1)
    roja_act = close < open_
    roja_prev = close.shift(1) < open_.shift(1)

    if p.require_2bars:
        ema_pos_l = (close > ema_val) & (close.shift(1) > ema_val.shift(1))
        ema_pos_s = (close < ema_val) & (close.shift(1) < ema_val.shift(1))
    else:
        ema_pos_l = close > ema_val
        ema_pos_s = close < ema_val

    color_l = (verde_act & verde_prev) if p.require_color else pd.Series(True, index=df.index)
    color_s = (roja_act & roja_prev) if p.require_color else pd.Series(True, index=df.index)

    dist_ema_pct = (close - ema_val).abs() / ema_val * 100.0
    if p.use_ema_dist:
        cond_dist = (dist_ema_pct >= p.min_ema_dist_pct) & (dist_ema_pct <= p.max_ema_dist_pct)
    else:
        cond_dist = pd.Series(True, index=df.index)

    if p.use_ema:
        cond_ema_l = ema_pos_l & color_l & ema_up & cond_dist
        cond_ema_s = ema_pos_s & color_s & ema_dn & cond_dist
    else:
        cond_ema_l = pd.Series(True, index=df.index)
        cond_ema_s = pd.Series(True, index=df.index)

    cond_rsi_l = (rsi_val < p.rsi_ob) if p.use_rsi else pd.Series(True, index=df.index)
    cond_rsi_s = (rsi_val > p.rsi_os) if p.use_rsi else pd.Series(True, index=df.index)
    cond_chop = (chop_val < p.chop_max) if p.use_chop else pd.Series(True, index=df.index)

    if p.use_zlag:
        cond_zlag_l = zt == 1
        cond_zlag_s = zt == -1
    else:
        cond_zlag_l = np.ones(len(df), dtype=bool)
        cond_zlag_s = np.ones(len(df), dtype=bool)

    cond_ema_l_a = cond_ema_l.to_numpy(bool)
    cond_ema_s_a = cond_ema_s.to_numpy(bool)
    cond_rsi_l_a = cond_rsi_l.to_numpy(bool)
    cond_rsi_s_a = cond_rsi_s.to_numpy(bool)
    cond_chop_a = cond_chop.to_numpy(bool)
    atr_ts_a = atr_ts.to_numpy(float)

    allow_long = p.trade_dir in ("Ambos", "Solo Long")
    allow_short = p.trade_dir in ("Ambos", "Solo Short")

    # Horas por vela para funding
    if len(df) > 1:
        deltas = pd.Series(df.index).diff().dropna()
        bar_hours = float(deltas.median().total_seconds() / 3600.0)
    else:
        bar_hours = 24.0
    funding_per_bar = p.funding_rate_8h * (bar_hours / 8.0)

    state = _State(p)
    equity = np.full(n, np.nan)
    pos_series = np.zeros(n, dtype=int)
    signals = pd.DataFrame(False, index=df.index, columns=["buy", "sell"])

    pending_entry = 0
    pending_entry_bar = -1

    for i in range(i0, n):
        # 0. Liquidación
        if state.position != 0 and i > state.entry_bar:
            if state.position == 1 and l[i] <= state.liq_price:
                raw = min(o[i], state.liq_price)
                _exit(state, i, raw, "liquidation", df, p)
            elif state.position == -1 and h[i] >= state.liq_price:
                raw = max(o[i], state.liq_price)
                _exit(state, i, raw, "liquidation", df, p)

        # 1. Stop de la vela (orden colocada al cierre anterior)
        if state.position != 0 and i > state.entry_bar:
            if state.position == 1 and l[i] <= state.stop_level:
                raw = min(o[i], state.stop_level)
                _exit(state, i, raw, "trailing" if state.ts_active else "stop", df, p)
            elif state.position == -1 and h[i] >= state.stop_level:
                raw = max(o[i], state.stop_level)
                _exit(state, i, raw, "trailing" if state.ts_active else "stop", df, p)

        # 2. Entrada pendiente (modo apertura siguiente)
        if state.position == 0 and pending_entry != 0 and i > pending_entry_bar:
            _enter(state, pending_entry, i, o[i], df, p)
            pending_entry = 0
            pending_entry_bar = -1
            if state.position == 1 and l[i] <= state.stop_level:
                _exit(state, i, state.stop_level, "stop", df, p)
            elif state.position == -1 and h[i] >= state.stop_level:
                _exit(state, i, state.stop_level, "stop", df, p)

        # 3. Señal de entrada
        if state.position == 0 or not p.one_way:
            can_long = (state.position == 0) if p.one_way else (state.position <= 0)
            can_short = (state.position == 0) if p.one_way else (state.position >= 0)

            trig_long = (
                pending[i] == 1
                and cond_ema_l_a[i]
                and cond_rsi_l_a[i]
                and cond_chop_a[i]
                and cond_zlag_l[i]
                and allow_long
                and can_long
            )
            trig_short = (
                pending[i] == -1
                and cond_ema_s_a[i]
                and cond_rsi_s_a[i]
                and cond_chop_a[i]
                and cond_zlag_s[i]
                and allow_short
                and can_short
            )

            if trig_long:
                if state.position == -1:
                    _exit(state, i, c[i], "reversal", df, p)
                if p.exec_mode == "close":
                    _enter(state, 1, i, c[i], df, p)
                else:
                    pending_entry = 1
                    pending_entry_bar = i
                signals.iat[i, 0] = True
            elif trig_short:
                if state.position == 1:
                    _exit(state, i, c[i], "reversal", df, p)
                if p.exec_mode == "close":
                    _enter(state, -1, i, c[i], df, p)
                else:
                    pending_entry = -1
                    pending_entry_bar = i
                signals.iat[i, 1] = True

        # 4. Actualización del trailing (incluye la vela de entrada)
        if state.position == 1:
            state.highest_price = max(state.highest_price, h[i])
            gain = (state.highest_price - state.entry_price) / state.entry_price
            if p.use_ts and not state.ts_active and gain >= p.ts_act_pct:
                state.ts_active = True
            if state.ts_active:
                state.stop_level = max(state.stop_level, state.highest_price - atr_ts_a[i] * p.ts_atr_mult)
        elif state.position == -1:
            state.lowest_price = min(state.lowest_price, l[i])
            gain = (state.entry_price - state.lowest_price) / state.entry_price
            if p.use_ts and not state.ts_active and gain >= p.ts_act_pct:
                state.ts_active = True
            if state.ts_active:
                state.stop_level = min(state.stop_level, state.lowest_price + atr_ts_a[i] * p.ts_atr_mult)

        # 5. Funding (aproximado, proporcional a las horas de la vela)
        if p.apply_funding and state.position != 0:
            funding = state.position * funding_per_bar * state.units * c[i]
            state.equity -= funding
            state.funding_paid += funding

        # 6. Marcar equity
        if state.position == 1:
            equity[i] = state.equity + state.units * (c[i] - state.entry_price)
        elif state.position == -1:
            equity[i] = state.equity + state.units * (state.entry_price - c[i])
        else:
            equity[i] = state.equity
        pos_series[i] = state.position

        # 7. Cuenta liquidada: sin capital no se puede seguir operando.
        # Se detiene el backtest y se deja el equity en 0 hasta el final.
        if state.position == 0 and state.equity <= 0:
            equity[i] = 0.0
            equity[i + 1 :] = 0.0
            break

    # Cerrar posición abierta al final
    if state.position != 0:
        _exit(state, n - 1, c[-1], "end_of_data", df, p)
        equity[-1] = state.equity

    equity_s = pd.Series(equity, index=df.index, name="equity").iloc[i0:]
    buy_hold_s = (
        close.iloc[i0:] / close.iloc[i0] * p.initial_capital
    ).rename("buy_hold")
    trades_df = pd.DataFrame(state.trades)

    metrics = _compute_metrics(
        equity_s, buy_hold_s, trades_df, pos_series[i0:], p, df
    )
    return BacktestResult(
        equity=equity_s,
        buy_hold=buy_hold_s,
        trades=trades_df,
        metrics=metrics,
        signals=signals.iloc[i0:],
        params=p,
    )


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
def _compute_metrics(
    equity: pd.Series,
    buy_hold: pd.Series,
    trades: pd.DataFrame,
    pos_series: np.ndarray,
    p: Params,
    df: pd.DataFrame,
) -> dict:
    eq = equity.dropna()
    if len(eq) == 0:
        return {}

    final = float(eq.iloc[-1])
    total_ret = final / p.initial_capital - 1.0
    days = max((eq.index[-1] - eq.index[0]).days, 1)
    years = days / 365.25
    cagr = (final / p.initial_capital) ** (1.0 / years) - 1.0 if years > 0 and final > 0 else np.nan

    running_max = eq.cummax()
    dd_series = eq / running_max - 1.0
    max_dd = float(dd_series.min())

    rets = eq.pct_change().dropna()
    bars_per_year = len(eq) / years if years > 0 else np.nan
    if final <= 0:
        # Cuenta liquidada: Sharpe/Sortino no son interpretables.
        sharpe = np.nan
        sortino = np.nan
    else:
        sharpe = (
            float(rets.mean() / rets.std(ddof=1) * np.sqrt(bars_per_year))
            if len(rets) > 1 and rets.std(ddof=1) > 0
            else np.nan
        )
        downside = rets[rets < 0]
        sortino = (
            float(rets.mean() / downside.std(ddof=1) * np.sqrt(bars_per_year))
            if len(downside) > 1 and downside.std(ddof=1) > 0
            else np.nan
        )

    if len(trades) > 0:
        wins = trades[trades["pnl"] > 0]
        losses = trades[trades["pnl"] <= 0]
        gross_profit = float(wins["pnl"].sum())
        gross_loss = float(abs(losses["pnl"].sum()))
        n_wins = int(len(wins))
        n_losses = int(len(losses))
        win_rate = len(wins) / len(trades)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf
        avg_win = float(wins["pnl"].mean()) if len(wins) else 0.0
        avg_loss = float(losses["pnl"].mean()) if len(losses) else 0.0
        expectancy = float(trades["pnl"].mean())
        avg_bars = float(trades["bars_held"].mean())
        total_funding = float(trades["funding_paid"].sum())
        liquidations = int((trades["exit_reason"] == "liquidation").sum())
    else:
        gross_profit = 0.0
        gross_loss = 0.0
        n_wins = 0
        n_losses = 0
        win_rate = 0.0
        profit_factor = np.nan
        avg_win = 0.0
        avg_loss = 0.0
        expectancy = 0.0
        avg_bars = 0.0
        total_funding = 0.0
        liquidations = 0

    # Drawdown "realizado": se evalúa el capital solo al cierre de cada operación,
    # sin el resultado flotante de la posición abierta.
    if len(trades) > 0:
        realized_eq = p.initial_capital + trades["pnl"].cumsum()
        peak_realized = realized_eq.cummax()
        max_dd_closed = float(min((realized_eq / peak_realized - 1.0).min(), 0.0))
        max_dd_closed_usdt = float(min((realized_eq - peak_realized).min(), 0.0))
    else:
        max_dd_closed = 0.0
        max_dd_closed_usdt = 0.0

    exposure = float((pos_series != 0).mean())
    bh_final = float(buy_hold.iloc[-1])
    bh_ret = bh_final / p.initial_capital - 1.0
    bh_dd = float((buy_hold / buy_hold.cummax() - 1.0).min())

    return {
        "initial_capital": p.initial_capital,
        "final_equity": final,
        "net_profit": final - p.initial_capital,
        "total_return": total_ret,
        "cagr": cagr,
        "max_dd": max_dd,
        "max_dd_closed": max_dd_closed,
        "max_dd_closed_usdt": max_dd_closed_usdt,
        "sharpe": sharpe,
        "sortino": sortino,
        "n_trades": int(len(trades)),
        "n_wins": n_wins,
        "n_losses": n_losses,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "expectancy": expectancy,
        "avg_bars_held": avg_bars,
        "exposure": exposure,
        "total_funding": total_funding,
        "liquidations": liquidations,
        "buy_hold_return": bh_ret,
        "buy_hold_max_dd": bh_dd,
        "start": eq.index[0],
        "end": eq.index[-1],
        "days": days,
    }


if __name__ == "__main__":
    df = load_data("bingx", "BTC/USDT:USDT", "4h", "2022-01-01", "2026-11-01")
    res = run_backtest(df, Params())
    for k, v in res.metrics.items():
        print(f"{k:>18}: {v}")
    if len(res.trades):
        print(res.trades.tail(10).to_string())
