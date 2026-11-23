"""Motor de backtest para Momentum Guard Pro.

Soporta:
- Datos de futuros perpetuos de BingX vía ccxt (fuente oficial).
- Datos de Binance Futures como referencia de largo plazo (7 años).
- Datos de Yahoo Finance (spot/acciones) como alternativa.
- Leverage, margen, funding y liquidación aproximada.
- Todos los parámetros de la estrategia original de Pine v6.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import ccxt
import numpy as np
import pandas as pd
import yfinance as yf

# Momento en que este módulo se cargó. La app lo compara con la fecha del
# archivo para recargarlo si se editó con el servidor ya corriendo (Python, y
# por lo tanto Streamlit, conserva en memoria los módulos ya importados).
LOADED_MTIME = Path(__file__).stat().st_mtime

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
    # "ATR" mide la distancia a la EMA en múltiplos de ATR (se adapta sola a la
    # volatilidad de cada moneda); "Pct" usa el porcentaje nominal histórico.
    dist_mode: str = "ATR"
    dist_atr_len: int = 14
    min_ema_dist_atr: float = 1.5
    max_ema_dist_atr: float = 6.0
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
    open_position: dict | None = None


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


def _ema_band_mask(df: pd.DataFrame, ema_val: pd.Series, p: Params) -> pd.Series:
    """True donde la distancia precio-EMA cae dentro de la banda elástica.

    En modo "ATR" la distancia se mide en múltiplos de ATR (se adapta sola a la
    volatilidad del activo); en modo "Pct" se mide en porcentaje nominal.
    """
    if not p.use_ema_dist:
        return pd.Series(True, index=df.index)
    close = df["Close"]
    if str(p.dist_mode).upper().startswith("ATR"):
        # Un ATR nulo (mercado congelado) deja la distancia en NaN y bloquea.
        band_atr = _atr(df, p.dist_atr_len).replace(0.0, np.nan)
        dist = (close - ema_val).abs() / band_atr
        return (dist >= p.min_ema_dist_atr) & (dist <= p.max_ema_dist_atr)
    dist = (close - ema_val).abs() / ema_val * 100.0
    return (dist >= p.min_ema_dist_pct) & (dist <= p.max_ema_dist_pct)


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
# Datos: Binance Futures (referencia de largo plazo)
# ---------------------------------------------------------------------------
# No reemplaza a BingX: sirve para validar la estrategia en regímenes que BingX
# ya no conserva (bull 2021, bear 2022, lateral 2023-24, etc.). Binance es otro
# mercado: precios, mechas, funding y liquidez no son idénticos a BingX.
_BINANCE_VISION = "https://data.binance.vision/data/futures/um"
_BINANCE_REST = "https://fapi.binance.com/fapi/v1/klines"
_BINANCE_TICKER = "https://fapi.binance.com/fapi/v1/ticker/price"
_BINANCE_TF = {"15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}
_BINANCE_UA = {"User-Agent": "Mozilla/5.0 (compatible; MomentumGuardPro/2.0)"}
_BINANCE_TTL_S = 6 * 3600  # el histórico viejo no cambia; la cola se completa
_BINANCE_EARLIEST_TTL_S = 7 * 86400
_BINANCE_WORKERS = 6
_BINANCE_RECENT_DAYS = 75  # fallback diario solo para meses recién cerrados


def normalize_binance_symbol(symbol: str) -> str:
    """AAVE/USDT:USDT, AAVE-USDT o aave -> AAVEUSDT (formato de Binance)."""
    s = symbol.strip().upper()
    if not s:
        return "BTCUSDT"
    for sep in ("/", ":", "-", "_"):
        if sep in s:
            s = s.split(sep)[0]
            break
    if not s.endswith(("USDT", "BUSD", "USDC")):
        s = f"{s}USDT"
    return s


def _binance_http(url: str, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, headers=_BINANCE_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _binance_to_datetime(values: pd.Series) -> pd.Series:
    """Convierte timestamps de Binance (ms o µs según el archivo) a UTC naive."""
    ts = pd.to_numeric(values, errors="coerce")
    valid = ts.dropna()
    if valid.empty:
        return pd.to_datetime(ts, unit="ms", utc=True).dt.tz_localize(None)
    biggest = float(valid.max())
    if biggest > 1e15:
        unit = "us"
    elif biggest > 1e12:
        unit = "ms"
    else:
        unit = "s"
    return pd.to_datetime(ts, unit=unit, utc=True).dt.tz_localize(None)


def _binance_read_zip(url: str) -> pd.DataFrame | None:
    """Lee un zip de velas de data.binance.vision. None si no existe."""
    try:
        raw = _binance_http(url)
        df = pd.read_csv(io.BytesIO(raw), compression="zip", header=None)
    except Exception:
        return None
    if not len(df):
        return None
    df = df.iloc[:, :6]
    df.columns = ["ts", "Open", "High", "Low", "Close", "Volume"]
    # Algunos archivos traen fila de encabezado.
    df = df[pd.to_numeric(df["ts"], errors="coerce").notna()].copy()
    for col in ("Open", "High", "Low", "Close", "Volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["ts"] = _binance_to_datetime(df["ts"])
    df = df.dropna(subset=["ts", "Open", "High", "Low", "Close"])
    if df.empty:
        return None
    df = df.set_index("ts").sort_index()
    return df[~df.index.duplicated(keep="last")]


def _binance_many(urls: list[str]) -> pd.DataFrame:
    """Descarga varios zips en paralelo y devuelve lo que exista."""
    frames: list[pd.DataFrame] = []
    if not urls:
        return pd.DataFrame()
    with ThreadPoolExecutor(max_workers=_BINANCE_WORKERS) as pool:
        for df in pool.map(_binance_read_zip, urls):
            if df is not None and len(df):
                frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames)
    return out[~out.index.duplicated(keep="last")].sort_index()


def _binance_daily(sym: str, timeframe: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    first = start.normalize()
    last = (end - pd.Timedelta(days=1)).normalize()
    if last < first:
        return pd.DataFrame()
    days = pd.date_range(first, last, freq="D")
    urls = [
        f"{_BINANCE_VISION}/daily/klines/{sym}/{timeframe}/{sym}-{timeframe}-{d:%Y-%m-%d}.zip"
        for d in days
    ]
    return _binance_many(urls)


def _binance_month(sym: str, timeframe: str, month_start: pd.Timestamp, month_end: pd.Timestamp, now: pd.Timestamp) -> pd.DataFrame:
    """Velas de un mes: zip mensual o, si todavía no salió, zips diarios."""
    name = month_start.strftime("%Y-%m")
    url = f"{_BINANCE_VISION}/monthly/klines/{sym}/{timeframe}/{sym}-{timeframe}-{name}.zip"
    df = _binance_read_zip(url)
    if df is not None and len(df):
        return df
    # El mes en curso o el anterior recién cerrado pueden no tener archivo
    # mensual todavía: se completa con los diarios de ese mes.
    if month_start >= now.normalize() - pd.Timedelta(days=_BINANCE_RECENT_DAYS):
        return _binance_daily(sym, timeframe, month_start, month_end)
    return pd.DataFrame()


def _binance_rest_range(symbol: str, timeframe: str, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.DataFrame:
    """Velas faltantes (mes en curso) desde la API REST de Binance Futures."""
    sym = normalize_binance_symbol(symbol)
    step_ms = _timeframe_ms(timeframe)
    start_ms = _to_ms(start_ts)
    end_ms = _to_ms(end_ts) - 1  # endTime es inclusivo
    rows: list[list] = []
    cursor = start_ms

    for _ in range(1000):
        url = (
            f"{_BINANCE_REST}?symbol={sym}&interval={timeframe}"
            f"&startTime={cursor}&endTime={end_ms}&limit=1500"
        )
        try:
            payload = json.loads(_binance_http(url).decode("utf-8"))
        except Exception as exc:
            raise ConnectionError(
                f"Binance no respondió al pedir velas de {sym}. "
                "Revisá tu conexión e intentá de nuevo en unos segundos."
            ) from exc
        if not isinstance(payload, list) or not payload:
            break
        rows.extend(payload)
        last = int(payload[-1][0])
        if last + step_ms > end_ms or len(payload) < 1500:
            break
        cursor = last + step_ms
        time.sleep(0.3)

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(
        [row[:6] for row in rows],
        columns=["ts", "Open", "High", "Low", "Close", "Volume"],
    )
    for col in ("Open", "High", "Low", "Close", "Volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.tz_localize(None)
    df = df.dropna(subset=["ts", "Open", "High", "Low", "Close"])
    df = df.set_index("ts").sort_index()
    df = df[(df.index >= start_ts) & (df.index < end_ts)]
    return df[~df.index.duplicated(keep="last")]


def find_earliest_binance(
    symbol: str, timeframe: str, max_age_s: float = _BINANCE_EARLIEST_TTL_S
) -> pd.Timestamp:
    """Fecha de listado del perpetuo en Binance (primera vela disponible)."""
    sym = normalize_binance_symbol(symbol)
    key = hashlib.md5(f"earliest_binance|{sym}|{timeframe}|v1".encode()).hexdigest()[:16]
    path = _cache_file(f"earliest_binance_{key}.json")
    if _is_fresh(path, max_age_s):
        try:
            return pd.Timestamp(json.loads(path.read_text(encoding="utf-8"))["ts"])
        except Exception:
            pass

    url = f"{_BINANCE_REST}?symbol={sym}&interval={timeframe}&startTime=0&limit=1"
    try:
        payload = json.loads(_binance_http(url).decode("utf-8"))
    except Exception as exc:
        raise ConnectionError(
            f"Binance no respondió al buscar el inicio de {sym}. "
            "Revisá tu conexión e intentá de nuevo."
        ) from exc
    if not isinstance(payload, list) or not payload:
        raise ValueError(
            f"Binance no tiene histórico de {sym} en {timeframe}. "
            "Verificá que el perpetuo exista en Binance Futures."
        )
    ts = pd.to_datetime(int(payload[0][0]), unit="ms", utc=True).tz_localize(None)
    try:
        path.write_text(json.dumps({"ts": str(ts)}), encoding="utf-8")
    except Exception:
        pass
    return ts


def load_binance_data(symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
    """OHLCV de Binance Futures: archivos mensuales + REST para el mes en curso.

    No requiere API key. La primera descarga de 7 años baja ~84 archivos
    mensuales en paralelo (1-3 minutos); después queda en la caché de disco y
    solo se completa la cola con la API REST.
    """
    sym = normalize_binance_symbol(symbol)
    if timeframe not in _BINANCE_TF:
        raise ValueError(
            f"Binance no ofrece velas de {timeframe}. "
            f"Timeframes disponibles: {', '.join(sorted(_BINANCE_TF))}."
        )

    start_ts = pd.Timestamp(start)
    end_ts = min(
        pd.Timestamp(end) + pd.Timedelta(days=1),
        pd.Timestamp.now("UTC").tz_localize(None),
    )

    # Si se pide antes del listado, Binance no tiene velas: se recorta.
    try:
        earliest = find_earliest_binance(symbol, timeframe)
        if start_ts < earliest:
            start_ts = earliest
    except (ConnectionError, ValueError):
        pass

    if start_ts >= end_ts:
        raise ValueError(
            f"El rango pedido para {sym} empieza después del último dato disponible."
        )

    now = pd.Timestamp.now("UTC").tz_localize(None)
    months: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    month = start_ts.replace(day=1)
    while month < end_ts:
        nxt = (month + pd.offsets.MonthBegin(1)).normalize()
        if nxt <= now:
            months.append((month, min(nxt, end_ts)))
        month = nxt

    frames: list[pd.DataFrame] = []
    if months:
        with ThreadPoolExecutor(max_workers=_BINANCE_WORKERS) as pool:
            futures = [
                pool.submit(_binance_month, sym, timeframe, m, e, now)
                for m, e in months
            ]
            for fut in futures:
                part = fut.result()
                if part is not None and len(part):
                    frames.append(part)

    if frames:
        out = pd.concat(frames)
        out = out[~out.index.duplicated(keep="last")].sort_index()
        out = out[(out.index >= start_ts) & (out.index < end_ts)]
    else:
        out = pd.DataFrame()

    # Huecos que los archivos no cubren: el tramo previo al primer zip
    # mensual (Binance Vision arranca en 2020-01 para varios símbolos) y la
    # cola del mes en curso. Se completan con la API REST.
    step = pd.Timedelta(timeframe)
    pieces: list[pd.DataFrame] = []
    if len(out):
        head_end = min(out.index.min(), end_ts)
        if start_ts < head_end:
            head = _binance_rest_range(symbol, timeframe, start_ts, head_end)
            if len(head):
                pieces.append(head)
        tail_start = out.index.max() + step
        if tail_start < end_ts:
            tail = _binance_rest_range(symbol, timeframe, tail_start, end_ts)
            if len(tail):
                pieces.append(tail)
    else:
        tail = _binance_rest_range(symbol, timeframe, start_ts, end_ts)
        if len(tail):
            pieces.append(tail)

    if pieces:
        out = pd.concat([out, *pieces]) if len(out) else pd.concat(pieces)
        out = out[~out.index.duplicated(keep="last")].sort_index()

    out = out[(out.index >= start_ts) & (out.index < end_ts)]
    out = out.dropna(subset=["Open", "High", "Low", "Close"])
    if len(out) == 0:
        raise ValueError(
            f"Binance no devolvió datos para {sym} en el rango solicitado. "
            "Revisá el símbolo y las fechas."
        )
    return out


def fetch_live_price_binance(symbol: str, max_retries: int = 3) -> float:
    """Último precio del perpetuo en Binance Futures."""
    sym = normalize_binance_symbol(symbol)
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            payload = json.loads(
                _binance_http(f"{_BINANCE_TICKER}?symbol={sym}", timeout=15).decode("utf-8")
            )
            price = payload.get("price")
            if price is None:
                raise ValueError(f"Binance no devolvió precio para {sym}.")
            return float(price)
        except Exception as exc:
            last_exc = exc
            if _is_retryable(exc):
                _sleep_before_retry(attempt)
            else:
                raise
    raise ConnectionError(
        "Binance no respondió al pedir el precio en vivo. "
        "Se muestra el último cierre de la vela."
    ) from last_exc


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


def _load_binance_cached(
    symbol: str,
    timeframe: str,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> pd.DataFrame:
    """Reutiliza una descarga previa y completa solo la cola con la API REST.

    Los archivos mensuales de Binance son inmutables, así que volver a bajar
    7 años cada vez que vence la caché sería un desperdicio. Si ya hay una
    descarga que cubre el inicio pedido, se pide únicamente lo que falta.
    """
    index = _load_index()
    try:
        effective_start = max(start_ts, find_earliest_binance(symbol, timeframe))
    except Exception:
        effective_start = start_ts
    best: pd.DataFrame | None = None
    for meta in index.values():
        if (
            meta.get("source") != "binance"
            or meta.get("symbol") != symbol
            or meta.get("interval") != timeframe
        ):
            continue
        path = _CACHE_DIR / str(meta.get("file", ""))
        if not path.exists():
            continue
        try:
            cached = pd.read_parquet(path)
        except Exception:
            continue
        if cached.empty:
            continue
        # Tolerancia de 3 días por si el listado o las primeras velas faltan.
        if cached.index.min() > effective_start + pd.Timedelta(days=3):
            continue
        if best is None or cached.index.max() > best.index.max():
            best = cached

    if best is None:
        return load_binance_data(
            symbol,
            timeframe,
            str(start_ts.date()),
            str((end_ts - pd.Timedelta(days=1)).date()),
        )

    step = pd.Timedelta(timeframe)
    last = best.index.max()
    if last + step < end_ts:
        tail = _binance_rest_range(symbol, timeframe, last + step, end_ts)
        if len(tail):
            best = pd.concat([best, tail])
            best = best[~best.index.duplicated(keep="last")].sort_index()
    return best[(best.index >= start_ts) & (best.index < end_ts)]


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
    los rangos ya cerrados se guardan 7 días. Binance usa una caché de 6 horas
    porque su histórico viejo no cambia y solo se completa la cola.
    """
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1)
    is_bingx = source.lower().startswith("bingx")
    is_binance = source.lower().startswith("binance")
    src = "bingx" if is_bingx else ("binance" if is_binance else "yahoo")

    if max_age_s is None:
        today = pd.Timestamp.now("UTC").tz_localize(None).normalize()
        if end_ts >= today:
            max_age_s = _BINANCE_TTL_S if is_binance else 900
        else:
            max_age_s = 7 * 86400

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
    elif is_binance:
        df = _load_binance_cached(symbol, interval, start_ts, end_ts)
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
        self.entry_commission = 0.0
        self.entry_raw = np.nan
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
    state.entry_raw = raw_price
    state.entry_commission = commission
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
    if p.exec_mode == "close":
        # La entrada es al cierre de la vela: su máximo/mínimo ya pasaron antes
        # de entrar, así que no cuentan para activar ni mover el trailing.
        state.highest_price = fill
        state.lowest_price = fill
    else:
        state.highest_price = float(df["High"].iloc[i]) if direction == 1 else np.nan
        state.lowest_price = float(df["Low"].iloc[i]) if direction == -1 else np.nan
    state.ts_active = False
    state.funding_paid = 0.0


def _exit(state: _State, i: int, raw_price: float, reason: str, df: pd.DataFrame, p: Params) -> None:
    direction = state.position
    fill = raw_price * (1.0 - direction * p.slippage)
    pnl_price = direction * state.units * (fill - state.entry_price)
    exit_commission = state.units * fill * p.commission
    state.equity += pnl_price - exit_commission
    if reason == "liquidation":
        state.equity = max(0.0, state.equity)

    pnl_total = state.equity - state.entry_equity
    ret = pnl_total / state.entry_equity * 100.0 if state.entry_equity else 0.0

    # Desglose por operación para poder separar el resultado del precio de los
    # gastos de operar:
    #   pnl_gross      = solo movimiento del precio (sin slippage ni gastos)
    #   pnl_price      = movimiento con los precios de ejecución (incluye slippage)
    #   fees           = comisión de entrada + comisión de salida + funding
    #   slippage_cost  = lo que cuesta ejecutar peor que el precio de la vela
    pnl_gross = direction * state.units * (raw_price - state.entry_raw)
    fees = state.entry_commission + exit_commission + state.funding_paid
    # Positivo = lo que costó ejecutar peor que el precio de la vela.
    slippage_cost = pnl_gross - pnl_price

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
            "pnl_price": pnl_price,
            "pnl_gross": pnl_gross,
            "fees": fees,
            "slippage_cost": slippage_cost,
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
    state.entry_commission = 0.0
    state.entry_raw = np.nan


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

    cond_dist = _ema_band_mask(df, ema_val, p)

    if p.use_ema:
        cond_ema_l = ema_pos_l & ema_up & cond_dist
        cond_ema_s = ema_pos_s & ema_dn & cond_dist
    else:
        cond_ema_l = pd.Series(True, index=df.index)
        cond_ema_s = pd.Series(True, index=df.index)

    cond_rsi_l = (rsi_val < p.rsi_ob) if p.use_rsi else pd.Series(True, index=df.index)
    cond_rsi_s = (rsi_val > p.rsi_os) if p.use_rsi else pd.Series(True, index=df.index)
    cond_chop = (chop_val < p.chop_max) if p.use_chop else pd.Series(True, index=df.index)

    if p.use_zlag:
        close_above_zlema = (close > zlema).to_numpy(bool)
        close_below_zlema = (close < zlema).to_numpy(bool)
        cond_zlag_l = (zt == 1) & close_above_zlema
        cond_zlag_s = (zt == -1) & close_below_zlema
    else:
        cond_zlag_l = np.ones(len(df), dtype=bool)
        cond_zlag_s = np.ones(len(df), dtype=bool)

    color_l_a = color_l.to_numpy(bool)
    color_s_a = color_s.to_numpy(bool)
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
                and color_l_a[i]
                and cond_rsi_l_a[i]
                and cond_chop_a[i]
                and cond_zlag_l[i]
                and allow_long
                and can_long
            )
            trig_short = (
                pending[i] == -1
                and cond_ema_s_a[i]
                and color_s_a[i]
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
        entrada_al_cierre = p.exec_mode == "close" and i == state.entry_bar
        if state.position == 1:
            if not entrada_al_cierre:
                state.highest_price = max(state.highest_price, h[i])
            gain = (state.highest_price - state.entry_price) / state.entry_price
            if p.use_ts and not state.ts_active and gain >= p.ts_act_pct:
                state.ts_active = True
            if state.ts_active:
                state.stop_level = max(state.stop_level, state.highest_price - atr_ts_a[i] * p.ts_atr_mult)
        elif state.position == -1:
            if not entrada_al_cierre:
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

    # La posición que quedó abierta al final NO se cierra artificialmente: el
    # equity ya está marcado a mercado en la última vela. Se devuelve aparte para
    # que la app la muestre como abierta y no invente una operación cerrada.
    open_position = None
    if state.position != 0:
        direction = state.position
        last_price = float(c[-1])
        floating = direction * state.units * (last_price - state.entry_price)
        pnl_net = (state.equity + floating) - state.entry_equity
        open_position = {
            "direction": "Long" if direction == 1 else "Short",
            "entry_time": state.entry_time,
            "entry_price": float(state.entry_price),
            "units": float(state.units),
            "notional": float(state.notional),
            "margin": float(state.margin),
            "stop_level": float(state.stop_level),
            "liq_price": float(state.liq_price),
            "last_price": last_price,
            "funding_paid": float(state.funding_paid),
            "entry_equity": float(state.entry_equity),
            "bars_held": int((n - 1) - state.entry_bar),
            "unrealized_pnl": float(floating),
            "pnl_net": float(pnl_net),
            "return_pct": (
                float(pnl_net / state.entry_equity * 100.0)
                if state.entry_equity
                else 0.0
            ),
        }

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
        open_position=open_position,
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
    # El importe en USD corresponde a esa misma caída (mismo valle), para que el
    # porcentaje y el dinero de la tarjeta cuenten el mismo episodio.
    i_dd = dd_series.idxmin()
    max_dd_usdt = float(eq.loc[i_dd] - running_max.loc[i_dd])

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
        worst_trade = float(trades["pnl"].min())
        best_trade = float(trades["pnl"].max())
        expectancy = float(trades["pnl"].mean())
        avg_bars = float(trades["bars_held"].mean())
        total_funding = float(trades["funding_paid"].sum())
        liquidations = int((trades["exit_reason"] == "liquidation").sum())

        # Resultado medido SOLO por el movimiento del precio, sin comisiones,
        # slippage ni funding. Sirve para ver cuánto pierde/gana la estrategia
        # por sus decisiones y cuánto se llevan los gastos de operar.
        if "pnl_gross" in trades:
            pg = trades["pnl_gross"]
            gross_profit_price = float(pg[pg > 0].sum())
            gross_loss_price = float(abs(pg[pg <= 0].sum()))
            total_fees = float(trades["fees"].sum())
            total_slippage = float(trades["slippage_cost"].sum())
        else:
            gross_profit_price = gross_profit
            gross_loss_price = gross_loss
            total_fees = 0.0
            total_slippage = 0.0
    else:
        gross_profit = 0.0
        gross_loss = 0.0
        n_wins = 0
        n_losses = 0
        win_rate = 0.0
        profit_factor = np.nan
        avg_win = 0.0
        avg_loss = 0.0
        worst_trade = 0.0
        best_trade = 0.0
        expectancy = 0.0
        avg_bars = 0.0
        total_funding = 0.0
        liquidations = 0
        gross_profit_price = 0.0
        gross_loss_price = 0.0
        total_fees = 0.0
        total_slippage = 0.0

    # Drawdown "realizado": se evalúa el capital solo al cierre de cada operación,
    # sin el resultado flotante de la posición abierta.
    if len(trades) > 0:
        realized_eq = p.initial_capital + trades["pnl"].cumsum()
        peak_realized = realized_eq.cummax()
        dd_closed = realized_eq / peak_realized - 1.0
        i_closed = dd_closed.idxmin()
        max_dd_closed = float(min(dd_closed.loc[i_closed], 0.0))
        max_dd_closed_usdt = float(
            min(realized_eq.loc[i_closed] - peak_realized.loc[i_closed], 0.0)
        )
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
        "max_dd_usdt": max_dd_usdt,
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
        "gross_profit_price": gross_profit_price,
        "gross_loss_price": gross_loss_price,
        "total_fees": total_fees,
        "total_slippage": total_slippage,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "worst_trade": worst_trade,
        "best_trade": best_trade,
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
