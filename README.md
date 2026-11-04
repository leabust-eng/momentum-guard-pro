# Momentum Guard Pro — Backtester

App local en Streamlit para backtestear la estrategia **Momentum Guard Pro** sobre
**futuros perpetuos de BingX**, con todos los parámetros configurables y sin el
límite de 2 meses de TradingView.

## Qué incluye

- Descarga de OHLCV reales de BingX vía `ccxt` (perpetuos lineales USDT).
- Alternativa Yahoo Finance para spot/acciones.
- **Modo "Desde el inicio disponible"** (`Periodo de análisis → Histórico
  completo`): detecta y usa automáticamente la vela más antigua que BingX
  conserva para el símbolo y timeframe elegidos.
  Incluye AAVE (`AAVE/USDT:USDT`) entre los símbolos predefinidos.
- **Selector de zona horaria**: las velas y operaciones se muestran por defecto
  en **UTC-3 (TradingView)**; también se puede ver en UTC. BingX entrega los
  datos en UTC, así que sin esto las horas quedaban 3 h corridas respecto del
  gráfico de TradingView. El cambio es solo de visualización.
- **Selector de periodo de análisis**: Histórico completo, últimos 7 / 30 / 60 /
  90 días o fechas exactas (Personalizado). El backtest arranca en la fecha
  elegida y usa velas previas solo como *warm-up* para que EMA 200, ZLEMA y
  CUSUM lleguen ya calentados; esas velas no operan ni cuentan en las métricas.
- Todos los parámetros de la estrategia original:
  - CUSUM (ventana, drift, umbral, confirmación).
  - EMA 200, pendiente, posición de precio, color de vela y banda elástica.
  - RSI y CHOP.
  - ZLEMA con banda dinámica.
  - Stop inicial, trailing por ATR, modo long/short/ambos.
- Configuración de futuros:
  - Leverage y margen por operación.
  - Comisión por lado y slippage.
  - Funding estimado cada 8h.
  - Margen de mantenimiento y liquidación aproximada.
- Métricas: retorno, CAGR, drawdown, Sharpe, Sortino, profit factor, win rate,
  exposición, funding total, liquidaciones y comparación con buy & hold.
- **Panel de riesgo en vivo**: con el precio real de BingX (se actualiza cada
  20 s) muestra el PnL de tu posición en USDT y % del capital, la distancia al
  stop y a la liquidación, y una tabla de "si desde acá el precio cae X %".
- Curva de equity, drawdown, precio con entradas/salidas y tabla de operaciones.
- Análisis de sensibilidad a un parámetro.
- **Mapa de calor del CUSUM** (threshold × drift): muestra si el resultado está en
  una meseta estable o en un pico aislado (sobreajuste). Se calcula bajo demanda.
- Descarga de operaciones en CSV.

## Configuración por defecto

La app abre con esta config (la sintonizada por el usuario), editable en la barra lateral:

| Bloque | Parámetro | Valor |
| --- | --- | --- |
| Cuenta | Capital inicial / leverage / margen | 3.000 USDT / 3× / 90 % |
| Futuros | Comisión / slippage | 0,05 % / 0,02 % por lado |
| Futuros | Funding / margen de mantenimiento | 0,01 % cada 8h (aplicado) / 0,5 % |
| CUSUM | Ventana / drift / umbral / confirmación | 30 / 0,5 / 5 / 1 vela |
| EMA | Periodo / pendiente | 200 / 1 |
| EMA | Confirmar 2 velas / continuidad de vela | No / Sí |
| Banda elástica | Distancia mínima / máxima | 1,0 % / 1,6 % |
| RSI | Periodo / long / short | 14 / 75 / 20 |
| CHOP | Ventana / ruido máximo | 14 / 50 |
| ZLEMA | Memoria / amplitud de banda | 70 / 2,2 |
| Riesgo | Stop inicial / trailing desde | 4 % / 2 % |
| Trailing | ATR / multiplicador | 14 / 6× |
| Ejecución | Modo | Cierre de vela (TV), long y short |

La ventana de análisis por defecto es **Histórico completo** (todo lo que BingX
conserva para el timeframe elegido).

## Instalación

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
streamlit run app.py
```

Se abre en `http://localhost:8501`.

### Arranque automático en Windows

- **`iniciar_app.bat`**: doble clic para levantar la app (mantiene la ventana
  abierta; cerrarla detiene el servidor).
- **`keep_alive.ps1`**: vigilante que reinicia Streamlit si el proceso muere y
  también si el proceso sigue vivo pero deja de responder (3 chequeos seguidos
  a `/_stcore/health` fallidos).
- **Tarea programada `MomentumGuardPro`**: lanza `keep_alive.vbs` (oculto) al
  iniciar sesión y además **cada 10 minutos**, así la app vuelve sola después de
  reiniciar la PC o si el propio vigilante hubiera muerto. El mutex
  `Global\MomentumGuardWatchdog` evita que queden vigilantes duplicados.

Para ver o cambiar la tarea: `Get-ScheduledTask -TaskName MomentumGuardPro`.
Para quitarla: `Unregister-ScheduledTask -TaskName MomentumGuardPro -Confirm:$false`.
Los reinicios del vigilante quedan registrados en `watchdog.log`.

## Deploy en Streamlit Community Cloud

La app se puede publicar gratis desde un repositorio de GitHub en
[share.streamlit.io](https://share.streamlit.io).

1. Subir el proyecto a GitHub:

   ```bash
   git init
   git add .
   git commit -m "Momentum Guard Pro"
   git branch -M main
   git remote add origin https://github.com/<usuario>/<repo>.git
   git push -u origin main
   ```

2. En share.streamlit.io → **Create app** → elegir el repo, branch `main` y
   main file `app.py`.
3. En **Advanced settings**, elegir Python 3.13.
4. **Deploy**.

Notas:

- No hay secretos ni API keys: no hace falta configurar nada.
- `.cache/` está en `.gitignore`; en Cloud se vuelve a descargar en cada
  arranque (tarda unos segundos la primera vez).
- La app se duerme tras un rato sin uso y despierta al abrirla.
- El arranque automático (`keep_alive.ps1`) es solo para Windows; en Cloud la
  plataforma se encarga de reiniciar el proceso.
- Si la IP del servidor no puede acceder a BingX, cambiá la fuente a
  **Yahoo Finance** en la barra lateral.
- **Vercel no es compatible**: Streamlit necesita un servidor persistente con
  WebSocket y las funciones de Vercel son efímeras.

## Estructura

```
momentum_guard/
├── app.py                 # Interfaz Streamlit
├── engine.py              # Datos, indicadores, backtest y métricas
├── requirements.txt
├── .streamlit/
│   └── config.toml        # Configuración del servidor
└── README.md
```

## Notas importantes

- **Histórico de BingX**: BingX **no** conserva todo el histórico en todos los
  timeframes. Aproximadamente: 15m ~100 días, 30m ~630 días, 1h desde abril
  2024, 4h desde septiembre 2022 y 1d desde la fecha de listado del símbolo
  (AAVE: 2021-11-09). La opción "Histórico completo" detecta la fecha exacta
  con una búsqueda binaria y la usa como inicio.
- **Warm-up**: para ventanas relativas o personalizadas la app descarga
  `max(320, EMA+50, ZLEMA×3+50)` velas antes del inicio y las usa solo para
  calcular indicadores. El equity, las operaciones y todas las métricas
  arrancan en la fecha elegida (100% de capital).
- **Caché en disco**: velas y fecha de inicio disponible se guardan en
  `.cache/` junto a `engine.py`. Reiniciar la app ya no vuelve a descargar todo.
  Los rangos que terminan hoy se refrescan cada 15 minutos; los históricos
  cerrados duran 7 días. El botón **🔄 Actualizar datos** borra la caché y
  fuerza una descarga si acaban de cerrar velas nuevas.
- **15m**: rangos largos tardan en descargar (BingX devuelve ~1.000 velas por
  petición). Para pruebas rápidas usa 60-90 días.
- **Funding**: se aplica de forma proporcional y constante (no usa el funding
  histórico real). Es una aproximación.
- **Liquidación**: se aproxima con el margen de mantenimiento; no modela el
  libro de órdenes ni el precio de liquidación exacto de BingX. Si el equity
  llega a 0, el backtest se detiene y las métricas se calculan hasta ese punto
  (Sharpe/Sortino/CAGR quedan sin valor).
- **Ejecución**: por defecto entra al cierre de la vela, como TradingView con
  `process_orders_on_close=true`. La opción "Apertura siguiente" es más realista.
- **Sin garantías**: un backtest no predice el futuro. Valida con forward test
  antes de arriesgar capital. No es asesoramiento financiero.
