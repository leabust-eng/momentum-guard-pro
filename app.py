"""App Streamlit: backtester configurable de Momentum Guard Pro para BingX."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date, timedelta

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from engine import (
    Params,
    clear_cache,
    fetch_live_price,
    find_earliest_bingx,
    load_archived_bars,
    load_data,
    run_backtest,
)

st.set_page_config(
    page_title="Momentum Guard Pro — Backtester",
    page_icon="📈",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 10px 14px;
    }
    div[data-testid="stMetricLabel"] { font-size: 0.8rem; opacity: 0.8; }
    div[data-testid="stMetricValue"] { font-size: 1.45rem; line-height: 1.6rem; }
    div[data-testid="stMetricValue"] > div {
        white-space: nowrap;
        overflow: visible;
        text-overflow: clip;
    }
    div[data-testid="stMetricDelta"] { font-size: 0.75rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📈 Momentum Guard Pro")
st.caption(
    "Backtester configurable para **futuros perpetuos de BingX**. "
    "Ajusta todos los parámetros, ejecuta y compara contra buy & hold."
)


# ---------------------------------------------------------------------------
# Caché
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=900)
def cached_load(source: str, symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
    return load_data(source, symbol, timeframe, start, end)


@st.cache_data(show_spinner=False, ttl=15)
def cached_live_price(symbol: str) -> float:
    return fetch_live_price(symbol)


@st.cache_data(show_spinner=False, ttl=300)
def cached_earliest(symbol: str, timeframe: str) -> str:
    return str(find_earliest_bingx(symbol, timeframe).date())


@st.cache_data(show_spinner=False, ttl=300)
def cached_archive_info(symbol: str, timeframe: str):
    df = load_archived_bars(symbol, timeframe)
    if df.empty:
        return None
    return len(df), df.index.min(), df.index.max()


TF_MINUTES = {
    "15m": 15, "30m": 30, "1h": 60, "2h": 120,
    "4h": 240, "6h": 360, "12h": 720, "1d": 1440,
}


# ---------------------------------------------------------------------------
# Sidebar: datos y ejecución
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("🌐 Datos")
    source = st.selectbox("Fuente", ["BingX Perpetuos", "Yahoo Finance"], index=0)
    is_bingx = source.startswith("BingX")

    if is_bingx:
        popular = [
            "AAVE/USDT:USDT", "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT",
            "BNB/USDT:USDT", "XRP/USDT:USDT", "DOGE/USDT:USDT", "AVAX/USDT:USDT",
            "LINK/USDT:USDT", "ADA/USDT:USDT", "LTC/USDT:USDT", "BCH/USDT:USDT",
            "OP/USDT:USDT",
        ]
        choice = st.selectbox(
            "Símbolos populares",
            ["(escribir manualmente)"] + popular,
            index=1,
        )
        if choice == "(escribir manualmente)":
            symbol = st.text_input("Símbolo BingX", value="AAVE/USDT:USDT", help="Ej: BTC/USDT:USDT, ETH/USDT:USDT")
        else:
            symbol = choice
    else:
        symbol = st.text_input("Símbolo Yahoo", value="BTC-USD", help="Ej: BTC-USD, ETH-USD, AAPL, SPY")

    timeframe = st.selectbox(
        "Timeframe",
        ["15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"],
        index=0,
    )

    tz_label = st.selectbox(
        "Zona horaria",
        ["UTC-3 (TradingView)", "UTC"],
        index=0,
        help=(
            "En qué horario se muestran las velas y las operaciones. BingX "
            "entrega los datos en UTC; TradingView los muestra en la hora local "
            "del gráfico (UTC-3 en Argentina)."
        ),
    )
    tz_offset_hours = -3 if tz_label.startswith("UTC-3") else 0

    today = date.today()
    if timeframe == "15m":
        default_start = today - timedelta(days=60)
    elif timeframe in ("30m", "1h"):
        default_start = today - timedelta(days=180)
    else:
        default_start = today - timedelta(days=730)

    earliest_date: date | None = None
    earliest_error: str | None = None
    if is_bingx:
        try:
            with st.spinner("Buscando inicio disponible..."):
                earliest_date = date.fromisoformat(cached_earliest(symbol, timeframe))
        except Exception as exc:
            earliest_error = str(exc)

    period = st.selectbox(
        "Periodo de análisis",
        [
            "Histórico completo",
            "Últimos 7 días",
            "Últimos 30 días",
            "Últimos 60 días",
            "Últimos 90 días",
            "Personalizado",
        ],
        index=0,
        help=(
            "Elegí una ventana relativa (por ejemplo, últimos 30 días) o fechas "
            "exactas. La ventana se mide desde las 00:00 del día de inicio en la "
            "zona horaria elegida."
        ),
    )
    relative_days = {
        "Últimos 7 días": 7,
        "Últimos 30 días": 30,
        "Últimos 60 días": 60,
        "Últimos 90 días": 90,
    }.get(period)

    if relative_days is not None:
        analysis_start = today - timedelta(days=relative_days)
        if earliest_date and analysis_start < earliest_date:
            analysis_start = earliest_date
    elif period == "Histórico completo":
        analysis_start = earliest_date or default_start
    else:
        analysis_start = default_start

    fixed_end = period.startswith("Últimos")

    col_a, col_b = st.columns(2)
    if period == "Personalizado":
        start_key = f"start_custom_{symbol}_{timeframe}"
        # Arranca en el inicio de la ventana que se estaba viendo.
        st.session_state.setdefault(
            start_key, st.session_state.get("last_analysis_start", default_start)
        )
        analysis_start = col_a.date_input(
            "Desde",
            disabled=False,
            key=start_key,
            help="Elegí la fecha exacta de inicio del análisis.",
        )
    else:
        st.session_state["last_analysis_start"] = analysis_start
        analysis_start = col_a.date_input(
            "Desde",
            value=analysis_start,
            disabled=True,
            key=f"start_{period}_{symbol}_{timeframe}",
            help="Cambiá a 'Personalizado' para editar la fecha de inicio.",
        )
    end_date = col_b.date_input(
        "Hasta",
        value=today,
        disabled=fixed_end,
        key=f"end_{period}_{symbol}_{timeframe}",
    )

    if earliest_error:
        st.caption(
            f"No se pudo detectar el inicio disponible ({earliest_error[:160]}). "
            "Se usa una fecha por defecto."
        )
    if period == "Histórico completo" and earliest_date:
        st.caption(
            f"Inicio más antiguo disponible: {earliest_date:%Y-%m-%d} "
            "(lo que conserva BingX + archivo propio)."
        )
    if is_bingx:
        arch = cached_archive_info(symbol, timeframe)
        if arch:
            n_arch, first_arch, last_arch = arch
            st.caption(
                f"Archivo propio: {n_arch:,} velas · "
                f"{first_arch:%Y-%m-%d} → {last_arch:%Y-%m-%d}."
            )

    if st.button(
        "🔄 Actualizar datos",
        help="Borra la caché local y vuelve a descargar velas (útil si acaban de cerrar velas nuevas).",
    ):
        clear_cache()
        st.cache_data.clear()
        st.rerun()

    initial_capital = st.number_input(
        "Capital inicial (USDT)", value=3_000.0, min_value=100.0, step=1_000.0
    )

    st.divider()
    st.header("⚙️ Futuros")
    leverage = st.slider("Leverage", 1.0, 20.0, 3.0, 0.5)
    position_pct = st.slider("Margen por operación (% equity)", 1, 100, 90) / 100.0
    commission_pct = st.number_input(
        "Comisión por lado (%)", value=0.05, min_value=0.0, step=0.01, format="%.3f"
    )
    slippage_pct = st.number_input(
        "Slippage (%)", value=0.02, min_value=0.0, step=0.01, format="%.3f"
    )
    apply_funding = st.checkbox("Aplicar funding", value=True)
    funding_pct = st.number_input(
        "Funding cada 8h (%)", value=0.01, min_value=-1.0, step=0.001, format="%.4f"
    )
    maintenance_pct = st.number_input(
        "Margen de mantenimiento (%)", value=0.5, min_value=0.0, step=0.1, format="%.2f"
    )
    exec_mode = st.selectbox(
        "Ejecución", ["Cierre de vela (TV)", "Apertura siguiente"], index=0
    )

    st.divider()
    st.header("🧠 Estrategia")

    with st.expander("1. CUSUM", expanded=False):
        cusum_vol_period = st.slider("Ventana de volatilidad", 5, 100, 30)
        cusum_drift = st.slider("Filtro de ruido", 0.05, 2.0, 0.5, 0.05)
        cusum_threshold = st.slider("Sensibilidad de señal", 0.5, 15.0, 5.0, 0.5)
        pending_bars = st.slider("Confirmación máxima (velas)", 1, 10, 1)

    with st.expander("2. Confirmación de mercado", expanded=False):
        use_ema = st.checkbox("Filtro de tendencia (EMA)", True)
        ema_len = st.slider("Periodo EMA", 20, 400, 200)
        ema_slope_bars = st.slider("Confirmación de dirección", 1, 10, 1)
        require_2bars = st.checkbox("Confirmar posición de precio (2 velas)", False)
        require_color = st.checkbox("Confirmar continuidad de vela", True)
        use_ema_dist = st.checkbox("Banda elástica (distancia a EMA)", True)
        min_ema_dist_pct = st.slider("Distancia mínima (%)", 0.0, 10.0, 1.0, 0.05)
        max_ema_dist_pct = st.slider("Distancia máxima (%)", 0.5, 20.0, 1.6, 0.1)
        use_rsi = st.checkbox("Filtro RSI", True)
        rsi_len = st.slider("Periodo RSI", 2, 50, 14)
        rsi_ob = st.slider("RSI límite superior long", 50.0, 90.0, 75.0, 1.0)
        rsi_os = st.slider("RSI límite inferior short", 10.0, 50.0, 20.0, 1.0)
        use_chop = st.checkbox("Filtro CHOP", True)
        chop_len = st.slider("Ventana CHOP", 5, 50, 14)
        chop_max = st.slider("Máximo ruido permitido", 30.0, 60.0, 50.0, 1.0)

    with st.expander("3. Resistencia dinámica (ZLEMA)", expanded=False):
        use_zlag = st.checkbox("Techo/piso dinámico", True)
        zlag_len = st.slider("Memoria ZLEMA", 5, 200, 70)
        zlag_mult = st.slider("Amplitud de banda", 0.1, 3.0, 2.2, 0.1)

    with st.expander("4. Protección de capital", expanded=False):
        trade_dir = st.selectbox("Modo operativo", ["Ambos", "Solo Long", "Solo Short"])
        one_way = st.checkbox("Operación única por activo", True)
        sl_pct = st.slider("Stop inicial (%)", 0.5, 15.0, 4.0, 0.1)
        use_ts = st.checkbox("Protección dinámica (trailing)", True)
        ts_act_pct = st.slider("Activar trailing tras ganancia (%)", 0.1, 10.0, 2.0, 0.1)
        ts_atr_len = st.slider("Periodo ATR trailing", 1, 50, 14)
        ts_atr_mult = st.slider("Amplitud trailing (× ATR)", 0.5, 12.0, 6.0, 0.5)


params = Params(
    cusum_vol_period=cusum_vol_period,
    cusum_drift=cusum_drift,
    cusum_threshold=cusum_threshold,
    pending_bars=pending_bars,
    use_ema=use_ema,
    ema_len=ema_len,
    ema_slope_bars=ema_slope_bars,
    require_2bars=require_2bars,
    require_color=require_color,
    use_ema_dist=use_ema_dist,
    min_ema_dist_pct=min_ema_dist_pct,
    max_ema_dist_pct=max_ema_dist_pct,
    use_rsi=use_rsi,
    rsi_len=rsi_len,
    rsi_ob=rsi_ob,
    rsi_os=rsi_os,
    use_chop=use_chop,
    chop_len=chop_len,
    chop_max=chop_max,
    use_zlag=use_zlag,
    zlag_len=zlag_len,
    zlag_mult=zlag_mult,
    trade_dir=trade_dir,
    one_way=one_way,
    sl_pct=sl_pct / 100.0,
    use_ts=use_ts,
    ts_act_pct=ts_act_pct / 100.0,
    ts_atr_len=ts_atr_len,
    ts_atr_mult=ts_atr_mult,
    leverage=leverage,
    position_pct=position_pct,
    maintenance_margin=maintenance_pct / 100.0,
    apply_funding=apply_funding,
    funding_rate_8h=funding_pct / 100.0,
    initial_capital=initial_capital,
    commission=commission_pct / 100.0,
    slippage=slippage_pct / 100.0,
    exec_mode="close" if exec_mode.startswith("Cierre") else "next_open",
)


# ---------------------------------------------------------------------------
# Carga de datos y backtest
# ---------------------------------------------------------------------------
warmup_bars = max(320, params.ema_len + 50, params.zlag_len * 3 + 50)
warmup_days = (
    int(np.ceil(warmup_bars * TF_MINUTES.get(timeframe, 60) / 1440)) + 2
)
load_start = analysis_start - timedelta(days=warmup_days)
if is_bingx and earliest_date and load_start < earliest_date:
    load_start = earliest_date

if is_bingx and timeframe == "15m" and (end_date - analysis_start).days > 180:
    st.warning(
        "Rango largo en 15m: la descarga de BingX puede tardar varios minutos. "
        "Para pruebas rápidas usa 60-90 días."
    )

if analysis_start >= end_date:
    st.error("La fecha 'Desde' debe ser anterior a 'Hasta'.")
    st.stop()

if min_ema_dist_pct > max_ema_dist_pct:
    st.warning(
        "La distancia mínima a la EMA es mayor que la máxima: "
        "la banda elástica bloqueará todas las entradas."
    )

with st.spinner("Descargando datos..."):
    try:
        df_all = cached_load(source, symbol, timeframe, str(load_start), str(end_date))
    except Exception as exc:
        st.error(f"No se pudieron cargar los datos ({type(exc).__name__}): {exc}")
        st.caption(
            "Suele ser un corte momentáneo de BingX o un límite de peticiones. "
            "Esperá unos segundos y probá 'Reintentar descarga'."
        )
        if st.button("🔄 Reintentar descarga"):
            clear_cache()
            st.cache_data.clear()
            st.rerun()
        st.stop()

if tz_offset_hours:
    # BingX entrega UTC: se desplaza el índice solo para mostrar (velas, tabla y gráficos).
    df_all = df_all.copy()
    df_all.index = df_all.index + pd.Timedelta(hours=tz_offset_hours)

analysis_ts = pd.Timestamp(analysis_start)
if getattr(df_all.index, "tz", None) is not None and analysis_ts.tzinfo is None:
    analysis_ts = analysis_ts.tz_localize(df_all.index.tz)

df = df_all[df_all.index >= analysis_ts]
if len(df) == 0:
    st.error("No hay velas en la ventana elegida. Revisá las fechas.")
    st.stop()

warmup_loaded = len(df_all) - len(df)
if 0 < warmup_loaded < warmup_bars:
    st.caption(
        f"Aviso: solo hay {warmup_loaded:,} velas antes del inicio de la ventana "
        f"(se buscaban ~{warmup_bars:,} para calentar los indicadores largos)."
    )

if len(df) < 50:
    st.warning(
        f"Solo hay {len(df)} velas. Se necesitan al menos ~300 para que los indicadores "
        "largos (EMA 200, ZLEMA 70) sean fiables. Amplía el rango de fechas."
    )
    st.stop()

with st.spinner("Ejecutando backtest..."):
    try:
        res = run_backtest(df_all, params, trade_start=analysis_ts)
    except Exception as exc:
        st.error(f"Error en el backtest: {exc}")
        st.stop()

m = res.metrics

warmup_txt = f" · warm-up {warmup_loaded:,} velas" if warmup_loaded > 0 else ""
st.caption(
    f"**{symbol}** · {timeframe} · ventana {df.index.min():%Y-%m-%d %H:%M} → "
    f"{df.index.max():%Y-%m-%d %H:%M} · {len(df):,} velas{warmup_txt} · "
    f"horario {tz_label} · fuente: {source}"
)


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
def pct(x: float) -> str:
    return f"{x * 100:+.2f}%" if pd.notna(x) else "—"


def num(x: float) -> str:
    return f"{x:,.2f}" if pd.notna(x) else "—"


pf = m["profit_factor"]
pf_display = "∞" if pf == np.inf else (f"{pf:.2f}" if pd.notna(pf) else "—")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Retorno total", pct(m["total_return"]), delta=f"{m['net_profit']:+,.0f} USDT")
c2.metric(
    "Máx. drawdown",
    pct(m["max_dd"]),
    help=(
        "Caída máxima de la equity vela a vela, incluyendo el resultado flotante "
        "de la posición abierta (lo que verías en la cuenta en vivo)."
    ),
)
c3.metric(
    "Máx. DD cerradas",
    pct(m["max_dd_closed"]),
    help=(
        "Caída máxima contando solo el capital al cierre de cada operación, sin "
        "resultado flotante. Es el número comparable a la 'Caída máx. del capital' "
        "cuando se calcula sobre trades cerrados."
    ),
)
c4.metric("Profit factor", pf_display)

c1, c2, c3 = st.columns(3)
c1.metric(
    "Operaciones",
    f"{m['n_trades']} // {m['n_wins']}",
    help=(
        f"{m['n_trades']} operaciones en total · {m['n_wins']} rentables · "
        f"{m['n_losses']} perdedoras. Se lee: total // rentables."
    ),
)
c2.metric("Aciertos", f"{m['win_rate'] * 100:.1f}%")
c3.metric("Buy & Hold", pct(m["buy_hold_return"]))

if m["n_trades"] > 0:
    st.markdown(
        f":green[**{m['n_wins']} rentables**] "
        f"({m['win_rate'] * 100:.1f} %) &nbsp;·&nbsp; "
        f":red[**{m['n_losses']} perdedoras**] "
        f"({(1 - m['win_rate']) * 100:.1f} %) &nbsp;·&nbsp; "
        f"**{m['n_trades']} operaciones** en total"
    )

c1, c2, c3 = st.columns(3)
c1.metric("CAGR", pct(m["cagr"]) if np.isfinite(m["cagr"]) else "—")
c2.metric("Sharpe", f"{m['sharpe']:.2f}" if np.isfinite(m["sharpe"]) else "—")
c3.metric("Exposición", f"{m['exposure'] * 100:.1f}%")

c1, c2, c3 = st.columns(3)
c1.metric("Funding total", f"{m['total_funding']:+,.2f} USDT")
c2.metric("Liquidaciones", f"{m['liquidations']}")
c3.metric("Equity final", f"{m['final_equity']:,.2f} USDT")

# Avisos de calidad
if m["final_equity"] <= 0:
    st.error(
        "Cuenta liquidada: el capital se agotó. El backtest se detuvo en ese punto. "
        "Revisa el leverage, el margen por operación y el stop."
    )
if m["n_trades"] == 0:
    st.warning(
        "No se generaron operaciones. Prueba a ampliar la banda elástica, "
        "cambiar el timeframe o relajar los filtros."
    )
elif m["n_trades"] < 30:
    st.warning(
        f"Muestra pequeña: {m['n_trades']} operaciones. "
        "Los resultados no son estadísticamente concluyentes."
    )
if np.isfinite(m["profit_factor"]) and m["profit_factor"] > 5:
    st.warning("Profit factor muy alto: posible sobreajuste o muestra pequeña.")
if m["max_dd"] < -0.30:
    st.warning("Drawdown superior al 30%: revisa el tamaño de posición y el leverage.")
if leverage > 1:
    st.info(
        "Leverage > 1: el motor aproxima liquidación y funding, pero el resultado real "
        "puede diferir. Haz forward test antes de arriesgar capital."
    )


# ---------------------------------------------------------------------------
# Impacto en el capital (riesgo de la posición)
# ---------------------------------------------------------------------------
_MOTIVOS = {
    "stop": "Stop inicial",
    "trailing": "Trailing stop",
    "reversal": "Señal contraria",
    "liquidation": "Liquidación",
}


@st.fragment(run_every="20s")
def live_capital_panel(
    params: Params,
    symbol: str,
    is_bingx: bool,
    fallback_price: float,
    tz_offset_hours: int,
    tz_label: str,
    result=None,
) -> None:
    """Posición abierta valorada con el precio real de BingX."""
    cap0 = float(params.initial_capital)
    lev = float(params.leverage)
    margen = cap0 * params.position_pct
    nocional = margen * lev
    costos = nocional * (2 * params.commission + 2 * params.slippage)
    dec = 2 if fallback_price >= 1 else 6

    col_a, col_b = st.columns(2)
    sentido = col_a.radio(
        "Dirección de tu posición",
        ["Long", "Short"],
        horizontal=True,
        key=f"live_sentido_{symbol}",
    )
    entrada = col_b.number_input(
        "Precio de entrada (USDT)",
        min_value=0.0,
        value=float(round(fallback_price, dec)),
        step=float(max(round(fallback_price * 0.001, dec), 10.0**-dec)),
        format=f"%.{dec}f",
        key=f"live_entrada_{symbol}",
    )
    d = 1 if sentido == "Long" else -1

    fuente = "último cierre de la vela"
    aviso = None
    if is_bingx:
        try:
            precio = float(cached_live_price(symbol))
            fuente = "BingX en vivo"
        except Exception as exc:
            precio = fallback_price
            aviso = f"No se pudo leer el precio en vivo: {exc}"
    else:
        precio = fallback_price

    if entrada <= 0 or precio <= 0:
        st.warning("Ingresá un precio de entrada mayor que cero.")
        return

    units = nocional / entrada
    pnl = units * (precio - entrada) * d - costos
    pnl_pct = pnl / cap0

    sl_price = entrada * (1.0 - d * params.sl_pct)
    liq_price = entrada * (1.0 - d * (1.0 / lev - params.maintenance_margin))
    room_sl = d * (precio - sl_price) / precio
    room_liq = d * (precio - liq_price) / precio

    hace = (precio / entrada - 1.0) * d

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Precio en vivo",
        f"{precio:,.{dec}f}",
        delta=f"{hace * 100:+.2f}% desde entrada",
        help=f"Fuente: {fuente}.",
    )
    m2.metric(
        "PnL ahora",
        f"{pnl:+,.0f} USDT",
        delta=f"{pnl_pct * 100:+.2f}% del capital",
        help=(
            "Resultado de la posición a este precio, neto de comisión y slippage "
            "de ida y vuelta."
        ),
    )
    m3.metric(
        "Stop",
        f"{sl_price:,.{dec}f}",
        delta=f"{room_sl * 100:+.2f}%",
        help=(
            f"Stop inicial a {params.sl_pct * 100:.1f}% del precio de entrada. "
            "El porcentaje es la distancia que le queda al precio actual: "
            "negativo significa que ya lo pasó."
        ),
    )
    m4.metric(
        "Liquidación",
        f"{liq_price:,.{dec}f}",
        delta=f"{room_liq * 100:+.2f}%",
        help="Precio de liquidación aproximado con el leverage configurado.",
    )

    hora = pd.Timestamp.now("UTC").tz_convert(None) + pd.Timedelta(hours=tz_offset_hours)
    st.caption(
        f"{fuente} · {hora:%H:%M:%S} ({tz_label}) · se actualiza cada 20 s · "
        f"{margen:,.0f} USDT de margen a {lev:g}× = {nocional:,.0f} USDT de exposición"
    )
    if aviso:
        st.caption(aviso)

    # La tabla muestra tu posición actual y, debajo, las operaciones que la
    # estrategia cerró con pérdida en la ventana elegida: exactamente los mismos
    # trades que aparecen en la pestaña "Operaciones". Sin escenarios inventados.
    filas: list[dict[str, str]] = [
        {
            "Fecha": "ahora",
            "Dirección": sentido,
            "Entrada": f"{entrada:,.{dec}f}",
            "Salida / actual": f"{precio:,.{dec}f}",
            "PnL": f"{pnl:+,.2f} USDT",
            "% capital": f"{pnl / cap0 * 100:+.2f} %",
            "Detalle": "Posición abierta",
        }
    ]
    perdidas = None
    if result is not None and len(result.trades):
        trades = result.trades
        perdidas = trades[trades["pnl"] < 0].sort_values("exit_time")
        for _, t in perdidas.iterrows():
            filas.append(
                {
                    "Fecha": f"{pd.Timestamp(t['exit_time']):%Y-%m-%d %H:%M}",
                    "Dirección": t["direction"],
                    "Entrada": f"{float(t['entry_price']):,.2f}",
                    "Salida / actual": f"{float(t['exit_price']):,.2f}",
                    "PnL": f"{float(t['pnl']):+,.2f} USDT",
                    "% capital": f"{float(t['return_pct']):+.2f} %",
                    "Detalle": (
                        f"{_MOTIVOS.get(t['exit_reason'], t['exit_reason'])} · "
                        f"entrada {pd.Timestamp(t['entry_time']):%d/%m %H:%M}"
                    ),
                }
            )

    st.dataframe(
        pd.DataFrame(filas),
        hide_index=True,
        width="stretch",
        column_config={
            "Fecha": st.column_config.TextColumn(
                width="small",
                help=(
                    "'ahora' es tu posición abierta; el resto son fechas de salida "
                    "de operaciones ya cerradas."
                ),
            ),
            "Dirección": st.column_config.TextColumn(width="small"),
            "Entrada": st.column_config.TextColumn(width="small"),
            "Salida / actual": st.column_config.TextColumn(
                width="small",
                help=(
                    "Precio de salida de la operación cerrada, o precio actual si "
                    "la posición sigue abierta."
                ),
            ),
            "PnL": st.column_config.TextColumn(width="small"),
            "% capital": st.column_config.TextColumn(
                width="small",
                help=(
                    "En la posición abierta es el PnL sobre el capital simulado. En "
                    "las operaciones cerradas es el retorno sobre el equity al "
                    "entrar, igual que en la pestaña 'Operaciones'."
                ),
            ),
            "Detalle": st.column_config.TextColumn(width="medium"),
        },
    )
    if perdidas is not None and perdidas.empty:
        st.caption("No hubo operaciones perdedoras en la ventana elegida.")
    st.caption(
        "La primera fila es tu **posición abierta** valorada al precio de BingX. "
        "Las demás son las **pérdidas de la estrategia** en la ventana elegida: "
        "las mismas operaciones que ves en la pestaña 'Operaciones', con su fecha "
        f"de salida (horario {tz_label})."
    )
    if room_sl <= 0:
        st.warning(
            "El precio actual ya está en el stop o más allá: la posición debería "
            "estar cerrada."
        )


with st.expander("🧮 ¿Cuánto me afecta una caída del precio?", expanded=True):
    cap0 = float(params.initial_capital)
    lev = float(params.leverage)
    margen_usado = cap0 * params.position_pct
    nocional = margen_usado * lev
    liq_move = max(1.0 / lev - params.maintenance_margin, 0.0)
    comisiones_pct_nocional = 2 * params.commission + 2 * params.slippage

    st.markdown("#### ⚡ Tu posición con el precio real")
    live_capital_panel(
        params,
        symbol,
        is_bingx,
        float(df["Close"].iloc[-1]),
        tz_offset_hours,
        tz_label,
        res,
    )

    st.divider()
    st.markdown("#### 📐 Escenario teórico (sin precio real)")
    k1, k2, k3 = st.columns(3)
    k1.metric(
        "Margen usado",
        f"{margen_usado:,.0f} USDT",
        help=f"{params.position_pct * 100:.0f}% del capital inicial.",
    )
    k2.metric(
        "Exposición (nocional)",
        f"{nocional:,.0f} USDT",
        help=f"Margen × {lev:g}× de apalancamiento.",
    )
    k3.metric(
        "Cada 1% de precio",
        f"−{nocional * 0.01:,.0f} USDT",
        help=(
            f"Con {lev:g}× y {params.position_pct * 100:.0f}% del capital, un "
            f"movimiento de 1% en contra equivale a "
            f"{nocional * 0.01 / cap0 * 100:.2f}% de tu capital."
        ),
    )

    movimientos = [
        (0.005, ""),
        (0.01, ""),
        (0.02, ""),
        (params.sl_pct, "Stop inicial configurado"),
        (0.10, ""),
        (liq_move, "Liquidación aproximada"),
    ]
    vistos: list[float] = []
    filas = []
    for frac, nota in movimientos:
        if frac <= 0 or any(abs(frac - v) < 1e-9 for v in vistos):
            continue
        vistos.append(frac)
        perdida = nocional * frac
        filas.append(
            {
                "Caída del precio": f"−{frac * 100:.2f} %",
                "Pérdida": f"−{perdida:,.0f} USDT",
                "% del capital": f"−{perdida / cap0 * 100:.2f} %",
                "Equity resultante": f"{cap0 - perdida:,.0f} USDT",
                "": nota,
            }
        )
    st.dataframe(
        pd.DataFrame(filas),
        hide_index=True,
        width="stretch",
        column_config={"Caída del precio": st.column_config.TextColumn(width="small")},
    )
    st.caption(
        f"Con {cap0:,.0f} USDT, {lev:g}× y {params.position_pct * 100:.0f}% de margen, "
        f"cada 1% de precio mueve tu capital {nocional / cap0:.2f}%. "
        f"El stop inicial ({params.sl_pct * 100:.1f}%) equivale a "
        f"−{params.sl_pct * nocional / cap0 * 100:.2f}% del capital. "
        f"Comisión + slippage de ida y vuelta ≈ "
        f"−{comisiones_pct_nocional * nocional / cap0 * 100:.2f}% del capital por operación. "
        "El trailing reemplaza al stop inicial en cuanto el precio avanza "
        f"{params.ts_act_pct * 100:.1f}% a tu favor."
    )


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------
def equity_chart(result, max_points: int = 2000) -> alt.Chart:
    eq = result.equity
    step = max(1, len(eq) // max_points)
    pos = list(range(0, len(eq), step))
    if pos[-1] != len(eq) - 1:
        pos.append(len(eq) - 1)
    data = pd.DataFrame(
        {
            "Fecha": eq.index[pos],
            "Estrategia": eq.to_numpy()[pos],
            "Buy & Hold": result.buy_hold.to_numpy()[pos],
        }
    ).melt("Fecha", var_name="Serie", value_name="Equity")
    return (
        alt.Chart(data)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("Fecha:T", title=None),
            y=alt.Y("Equity:Q", title="Equity (USDT)", scale=alt.Scale(zero=False)),
            color=alt.Color(
                "Serie:N",
                scale=alt.Scale(domain=["Estrategia", "Buy & Hold"], range=["#00c896", "#5b8ff9"]),
                title=None,
            ),
            tooltip=[
                alt.Tooltip("Fecha:T", title="Fecha"),
                alt.Tooltip("Serie:N", title="Serie"),
                alt.Tooltip("Equity:Q", format=",.2f", title="Equity"),
            ],
        )
        .properties(height=360, title="Curva de equity")
        .interactive()
    )


def drawdown_chart(result, max_points: int = 2000) -> alt.Chart:
    dd = (result.equity / result.equity.cummax() - 1.0) * 100.0
    step = max(1, len(dd) // max_points)
    data = pd.DataFrame({"Fecha": dd.index[::step], "Drawdown": dd.to_numpy()[::step]})
    return (
        alt.Chart(data)
        .mark_area(color="#ff4b4b", opacity=0.55)
        .encode(
            x=alt.X("Fecha:T", title=None),
            y=alt.Y("Drawdown:Q", title="Drawdown (%)"),
            tooltip=[
                alt.Tooltip("Fecha:T", title="Fecha"),
                alt.Tooltip("Drawdown:Q", format=".2f", title="Drawdown %"),
            ],
        )
        .properties(height=170, title="Drawdown")
    )


def price_chart(data: pd.DataFrame, result, max_points: int = 2000) -> alt.Chart:
    step = max(1, len(data) // max_points)
    price_df = pd.DataFrame(
        {"Fecha": data.index[::step], "Cierre": data["Close"].to_numpy()[::step]}
    )
    base = (
        alt.Chart(price_df)
        .mark_line(color="#8a8a8a", strokeWidth=1)
        .encode(
            x=alt.X("Fecha:T", title=None),
            y=alt.Y("Cierre:Q", title="Precio", scale=alt.Scale(zero=False)),
        )
    )
    if len(result.trades) == 0:
        return base.properties(height=340, title="Precio")

    trades = result.trades
    entries = pd.DataFrame(
        {
            "Fecha": pd.to_datetime(trades["entry_time"]),
            "Precio": trades["entry_price"],
            "Tipo": "Entrada " + trades["direction"],
        }
    )
    exits = pd.DataFrame(
        {
            "Fecha": pd.to_datetime(trades["exit_time"]),
            "Precio": trades["exit_price"],
            "Tipo": "Salida " + trades["direction"],
        }
    )
    points = pd.concat([entries, exits], ignore_index=True)
    markers = (
        alt.Chart(points)
        .mark_point(filled=True, size=70)
        .encode(
            x=alt.X("Fecha:T", title=None),
            y=alt.Y("Precio:Q", scale=alt.Scale(zero=False)),
            color=alt.Color("Tipo:N", scale=alt.Scale(scheme="set1"), title=None),
            shape=alt.Shape("Tipo:N", title=None),
            tooltip=[
                alt.Tooltip("Fecha:T", title="Fecha"),
                alt.Tooltip("Precio:Q", format=",.4f", title="Precio"),
                alt.Tooltip("Tipo:N", title="Tipo"),
            ],
        )
    )
    return (base + markers).properties(height=340, title="Precio y operaciones")


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_resumen, tab_ops, tab_sens, tab_params = st.tabs(
    ["📊 Resumen", "📋 Operaciones", "🔍 Sensibilidad", "🧾 Parámetros"]
)

with tab_resumen:
    st.altair_chart(equity_chart(res), width="stretch")
    st.altair_chart(drawdown_chart(res), width="stretch")

with tab_ops:
    st.altair_chart(price_chart(df, res), width="stretch")
    if len(res.trades) == 0:
        st.info("No hay operaciones para mostrar.")
    else:
        trades = res.trades.copy()
        trades["entry_time"] = pd.to_datetime(trades["entry_time"]).dt.strftime("%Y-%m-%d %H:%M")
        trades["exit_time"] = pd.to_datetime(trades["exit_time"]).dt.strftime("%Y-%m-%d %H:%M")
        cols = [
            "entry_time", "exit_time", "direction", "entry_price", "exit_price",
            "pnl", "return_pct", "funding_paid", "bars_held", "exit_reason",
        ]
        st.dataframe(
            trades[cols],
            width="stretch",
            hide_index=True,
            column_config={
                "entry_time": "Entrada",
                "exit_time": "Salida",
                "direction": "Dirección",
                "entry_price": st.column_config.NumberColumn("Precio entrada", format="%.4f"),
                "exit_price": st.column_config.NumberColumn("Precio salida", format="%.4f"),
                "pnl": st.column_config.NumberColumn("PnL (USDT)", format="%.2f"),
                "return_pct": st.column_config.NumberColumn("Retorno %", format="%.2f"),
                "funding_paid": st.column_config.NumberColumn("Funding (USDT)", format="%.2f"),
                "bars_held": "Velas",
                "exit_reason": "Motivo",
            },
        )
        st.download_button(
            "⬇️ Descargar operaciones (CSV)",
            trades[cols].to_csv(index=False).encode("utf-8"),
            file_name=f"trades_{symbol.replace('/', '_')}_{timeframe}.csv",
            mime="text/csv",
        )

with tab_sens:
    st.subheader("Sensibilidad a un parámetro")
    st.caption(
        "Ejecuta la estrategia variando un parámetro y observa si el edge es robusto. "
        "Si el resultado se desploma con pequeños cambios, hay sobreajuste."
    )
    sens_specs = {
        "cusum_threshold": {"label": "Sensibilidad CUSUM", "lo": 1.0, "hi": 15.0, "scale": 1.0},
        "cusum_drift": {"label": "Filtro de ruido CUSUM", "lo": 0.1, "hi": 2.0, "scale": 1.0},
        "max_ema_dist_pct": {"label": "Distancia máxima EMA (%)", "lo": 0.5, "hi": 20.0, "scale": 1.0},
        "min_ema_dist_pct": {"label": "Distancia mínima EMA (%)", "lo": 0.0, "hi": 5.0, "scale": 1.0},
        "sl_pct": {"label": "Stop inicial (%)", "lo": 1.0, "hi": 10.0, "scale": 0.01},
        "ts_atr_mult": {"label": "Trailing (× ATR)", "lo": 1.0, "hi": 12.0, "scale": 1.0},
        "zlag_mult": {"label": "Amplitud ZLEMA", "lo": 0.2, "hi": 3.0, "scale": 1.0},
        "chop_max": {"label": "CHOP máximo", "lo": 30.0, "hi": 60.0, "scale": 1.0},
    }
    param_key = st.selectbox(
        "Parámetro", list(sens_specs.keys()), format_func=lambda k: sens_specs[k]["label"]
    )
    spec = sens_specs[param_key]
    n_steps = st.slider("Número de valores", 3, 15, 7)
    values = np.linspace(spec["lo"], spec["hi"], n_steps)

    if st.button("Ejecutar análisis de sensibilidad"):
        rows = []
        progress = st.progress(0.0)
        for j, value in enumerate(values):
            pp = replace(params, **{param_key: float(value) * spec["scale"]})
            rr = run_backtest(df_all, pp, trade_start=analysis_ts)
            rows.append(
                {
                    "valor": float(value),
                    "retorno_%": rr.metrics["total_return"] * 100.0,
                    "profit_factor": rr.metrics["profit_factor"],
                    "max_dd_%": rr.metrics["max_dd"] * 100.0,
                    "operaciones": rr.metrics["n_trades"],
                }
            )
            progress.progress((j + 1) / len(values))
        sens = pd.DataFrame(rows)
        st.dataframe(sens, width="stretch", hide_index=True)
        chart = (
            alt.Chart(sens)
            .mark_line(point=True, color="#00c896")
            .encode(
                x=alt.X("valor:Q", title=spec["label"]),
                y=alt.Y("retorno_%:Q", title="Retorno (%)"),
                tooltip=[
                    alt.Tooltip("valor:Q", title="Valor"),
                    alt.Tooltip("retorno_%:Q", format=".2f", title="Retorno %"),
                    alt.Tooltip("profit_factor:Q", format=".2f", title="PF"),
                    alt.Tooltip("max_dd_%:Q", format=".2f", title="Max DD %"),
                    alt.Tooltip("operaciones:Q", title="Ops"),
                ],
            )
            .properties(height=300, title="Retorno vs parámetro")
        )
        st.altair_chart(chart, width="stretch")

    st.divider()
    st.subheader("Mapa de calor del CUSUM")
    st.caption(
        "Barre una grilla de sensibilidad (threshold) × filtro de ruido (drift) "
        "manteniendo el resto de los parámetros. Una meseta amplia indica robustez; "
        "un pico aislado indica sobreajuste."
    )
    th_options = [2.0, 3.0, 4.0, 4.5, 5.0, 5.5, 6.0, 7.0, 8.0, 10.0]
    dr_options = [0.3, 0.4, 0.45, 0.5, 0.55, 0.6, 0.7, 0.8]
    th_range = st.select_slider(
        "Rango de sensibilidad CUSUM",
        options=th_options,
        value=(3.0, 8.0),
    )
    dr_range = st.select_slider(
        "Rango de filtro de ruido",
        options=dr_options,
        value=(0.4, 0.7),
    )
    th_values = [v for v in th_options if th_range[0] <= v <= th_range[1]]
    dr_values = [v for v in dr_options if dr_range[0] <= v <= dr_range[1]]
    map_metric = st.selectbox(
        "Métrica del mapa", ["Retorno %", "Profit factor", "Máx. drawdown %"]
    )
    heat_key = (
        symbol, timeframe, str(analysis_start), str(end_date), repr(params),
        tuple(th_values), tuple(dr_values),
    )
    if st.button("Calcular mapa de calor CUSUM"):
        rows = []
        total = len(th_values) * len(dr_values)
        progress = st.progress(0.0)
        done = 0
        for th in th_values:
            for dr in dr_values:
                rr = run_backtest(
                    df_all,
                    replace(params, cusum_threshold=th, cusum_drift=dr),
                    trade_start=analysis_ts,
                )
                mm = rr.metrics
                rows.append(
                    {
                        "threshold": th,
                        "drift": dr,
                        "retorno_%": mm["total_return"] * 100.0,
                        "profit_factor": mm["profit_factor"],
                        "max_dd_%": mm["max_dd"] * 100.0,
                        "operaciones": mm["n_trades"],
                    }
                )
                done += 1
                progress.progress(done / total)
        progress.empty()
        st.session_state["cusum_map"] = {"key": heat_key, "data": pd.DataFrame(rows)}

    stored_map = st.session_state.get("cusum_map")
    if stored_map and stored_map["key"] == heat_key:
        heat = stored_map["data"]
        metric_col = {
            "Retorno %": "retorno_%",
            "Profit factor": "profit_factor",
            "Máx. drawdown %": "max_dd_%",
        }[map_metric]
        if metric_col == "retorno_%":
            color_scale = alt.Scale(scheme="redyellowgreen", domainMid=0)
            fmt = ".1f"
        elif metric_col == "profit_factor":
            color_scale = alt.Scale(scheme="viridis")
            fmt = ".2f"
        else:
            color_scale = alt.Scale(scheme="reds", reverse=True)
            fmt = ".1f"

        base = alt.Chart(heat).encode(
            x=alt.X("threshold:O", title="Sensibilidad CUSUM (threshold)"),
            y=alt.Y("drift:O", title="Filtro de ruido (drift)"),
        )
        heatmap = base.mark_rect(stroke="white", strokeWidth=1).encode(
            color=alt.Color(f"{metric_col}:Q", title=map_metric, scale=color_scale),
            tooltip=[
                alt.Tooltip("threshold:O", title="Threshold"),
                alt.Tooltip("drift:O", title="Drift"),
                alt.Tooltip("retorno_%:Q", format=".2f", title="Retorno %"),
                alt.Tooltip("profit_factor:Q", format=".2f", title="PF"),
                alt.Tooltip("max_dd_%:Q", format=".2f", title="Max DD %"),
                alt.Tooltip("operaciones:O", title="Ops"),
            ],
        )
        layers = [heatmap]
        if (
            params.cusum_threshold in th_values
            and params.cusum_drift in dr_values
        ):
            current = pd.DataFrame(
                [{"threshold": params.cusum_threshold, "drift": params.cusum_drift}]
            )
            layers.append(
                alt.Chart(current)
                .mark_point(
                    size=220, filled=False, stroke="black", strokeWidth=2, shape="square"
                )
                .encode(x="threshold:O", y="drift:O")
            )
        st.altair_chart(
            alt.layer(*layers).properties(
                height=max(220, 45 * len(dr_values)),
                title=f"{map_metric} según CUSUM (cuadrado negro = configuración actual)",
            ),
            width="stretch",
        )

        best = heat.loc[heat["retorno_%"].idxmax()]
        st.caption(
            f"Mejor retorno de la grilla: threshold={best['threshold']:g}, "
            f"drift={best['drift']:g} → {best['retorno_%']:.2f}% "
            f"(PF {best['profit_factor']:.2f}, DD {best['max_dd_%']:.2f}%, "
            f"{int(best['operaciones'])} ops)."
        )
        if best["threshold"] in (th_values[0], th_values[-1]) or best["drift"] in (
            dr_values[0],
            dr_values[-1],
        ):
            st.warning(
                "El mejor valor está en el borde de la grilla. Ampliá el rango antes "
                "de sacar conclusiones."
            )
        st.dataframe(
            heat.sort_values("retorno_%", ascending=False).head(10),
            width="stretch",
            hide_index=True,
            column_config={
                "threshold": st.column_config.NumberColumn("Threshold", format="%.1f"),
                "drift": st.column_config.NumberColumn("Drift", format="%.2f"),
                "retorno_%": st.column_config.NumberColumn("Retorno %", format="%.2f"),
                "profit_factor": st.column_config.NumberColumn("PF", format="%.2f"),
                "max_dd_%": st.column_config.NumberColumn("Max DD %", format="%.2f"),
                "operaciones": st.column_config.NumberColumn("Ops", format="%d"),
            },
        )
        st.caption(
            "Si el máximo está rodeado de valores mucho peores, el resultado depende "
            "de esa combinación exacta. Buscá una zona estable, no el número más alto."
        )
    elif stored_map:
        st.info(
            "El mapa guardado corresponde a otra configuración o a otro rango. "
            "Volvé a calcularlo para actualizarlo."
        )

with tab_params:
    st.subheader("Parámetros activos")
    st.json(asdict(params))
    st.caption(
        "Backtest aproximado: no modela libros de órdenes, latencia ni funding real variable. "
        "No es asesoramiento financiero. Valida con forward test."
    )
