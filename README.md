# Momentum Guard Pro — Backtester

App local en Streamlit para backtestear la estrategia **Momentum Guard Pro** sobre
**futuros perpetuos**. BingX es la fuente oficial y por defecto; **Binance
Futures** se suma como fuente alternativa de **muy largo plazo** (hasta 7 años)
para validar la estrategia en regímenes que BingX ya no conserva.

## Qué incluye

- Descarga de OHLCV reales de BingX vía `ccxt` (perpetuos lineales USDT).
- **Fuente Binance Futures (largo plazo)**: 7 años de velas desde
  `data.binance.vision` + API REST para el mes en curso, sin API key. No
  reemplaza a BingX: sirve para validar bull/bear/lateral y walk-forward largo.
- Alternativa Yahoo Finance para spot/acciones.
- **Modo "Desde el inicio disponible"** (`Periodo de análisis → Histórico
  completo`): detecta y usa automáticamente la vela más antigua que BingX
  conserva para el símbolo y timeframe elegidos.
  Incluye AAVE (`AAVE/USDT:USDT`) entre los símbolos predefinidos. La lista
  actual tiene 14 pares: AAVE, BTC, ETH, SOL, BNB, XRP, DOGE, AVAX, LINK, ADA,
  LTC, BCH, OP y AXS.
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
  - EMA 200, pendiente, posición de precio, color de vela y banda elástica
    (en % fijo o en múltiplos de ATR, seleccionable).
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
- **Buy & Hold** (la referencia): comprar el activo con todo el capital al primer
  cierre de la ventana y no tocarlo hasta el final, sin leverage, sin comisiones,
  sin funding y sin stops. Es, básicamente, el retorno del precio en esa ventana.
  Sirve para responder una sola pregunta: **¿la estrategia aportó algo o el
  mercado subió solo?** Si el retorno de la estrategia queda por debajo del
  buy & hold, un simple "comprar y mantener" habría rendido más en ese período.
  No es una comparación de riesgo equivalente: el buy & hold va sin
  apalancamiento y la estrategia usa 3×, así que también hay que mirar los
  drawdowns (el tooltip de la métrica muestra el del buy & hold).
- El **retorno total** se calcula sobre el capital inicial, no sobre la
  exposición: con 3× y 100 % de margen la exposición es 9.000 USDT, así que un
  +11,76 % de retorno son +352,78 USDT sobre 3.000 (y equivalen a +3,92 % sobre
  la exposición). La app muestra el desglose debajo de las métricas.
- El **equity final** = capital inicial + resultado del precio − slippage −
  comisiones ± funding (+ resultado flotante si queda una posición abierta). El
  nocional no se suma: es el tamaño de la posición, no capital. La app lo
  desglosa en el panel "¿Cómo se compone el equity final?".
- **Panel de riesgo en vivo**: con el precio real de BingX (se actualiza cada
  20 s) muestra el PnL de tu posición en USDT y % del capital, la distancia al
  stop y a la liquidación, y una tabla de "si desde acá el precio cae X %".
- **Posición abierta sincronizada**: por defecto el panel valora la posición que
  la estrategia dejó abierta al final de la ventana (misma dirección, entrada y
  unidades que el backtest); el modo **Manual** permite simular una entrada
  propia. La posición abierta ya no se cierra artificialmente: figura con salida
  "abierta" en la pestaña Operaciones y no cuenta como operación cerrada en las
  métricas.
- Curva de equity, drawdown, precio con entradas/salidas y tabla de operaciones.
- **Presets optimizados por símbolo**: el selector *Preset de estrategia* del
  sidebar carga parámetros encontrados con búsqueda aleatoria y validados con
  walk-forward en 3 bloques temporales (OP, AVAX, LINK, BTC y AXS). Cambia
  también el símbolo. AAVE y ETH no necesitan preset: con la configuración actual
  ya ganan en los 3 bloques.
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
| Banda elástica | Unidad / distancia mínima / máxima | ATR (× 1,5 / 6,0) · o % (1,0 % / 1,6 %) |
| RSI | Periodo / long / short | 14 / 75 / 20 |
| CHOP | Ventana / ruido máximo | 14 / 50 |
| ZLEMA | Memoria / amplitud de banda | 70 / 2,2 |
| Riesgo | Stop inicial / trailing desde | 4 % / 2 % |
| Trailing | ATR / multiplicador | 14 / 6× |
| Ejecución | Modo | Cierre de vela (TV), long y short |

La ventana de análisis por defecto es **Histórico completo** (todo lo que BingX
conserva para el timeframe elegido). Con la fuente Binance, "Histórico completo"
arranca en la fecha de listado del perpetuo (BTCUSDT 15m: 2019-09-08).

### Banda elástica: ATR adaptativo vs porcentaje fijo

`Unidad de la banda` (sidebar → *2. Confirmación de mercado*) elige cómo se mide
la distancia entre el precio y la EMA 200:

- **ATR adaptativo** (por defecto): `|Close − EMA| / ATR(14)`. La banda se
  estira o encoge con la volatilidad real del activo, así que el mismo ajuste
  sirve para BTC y para una altcoin. Referencia con la muestra actual:

  | Activo | ATR% medio | 1,5× ATR | 6× ATR |
  | --- | --- | --- | --- |
  | BTC | 0,24 % | 0,36 % | 1,44 % |
  | ETH | 0,33 % | 0,49 % | 1,96 % |
  | AAVE | 0,59 % | 0,89 % | 3,55 % |

- **Porcentaje fijo**: la distancia nominal histórica (1,0 % / 1,6 % por
  defecto). Es el modo con el que se optimizaron los presets, así que al cargar
  un preset la app lo fuerza.

Medición 2026-07-27 → 2026-11-12 (BingX 15m, 3.000 USDT, 3×, 90 %):

| Banda | AAVE | BTC | ETH |
| --- | --- | --- | --- |
| % 1,0 / 1,6 | +342 % | −34 % | +140 % |
| % 1,0 / 4,0 | +193 % | −47 % | +144 % |
| ATR 1,5 / 6,0 | +50 % | −19 % | +73 % |

El modo ATR no es "mejor" por sí solo: cambia la regla. Su ventaja es que no hay
que recalibrar los números por moneda. Antes de operar, reoptimizá los límites
en ATR con la muestra completa; tres meses no alcanzan para concluir.

## Fuente Binance Futures (referencia de largo plazo)

El selector **Fuente** agrega `Binance Futures (largo plazo)` **después** de
BingX, que sigue siendo la opción por defecto. La fuente Binance:

- Baja los archivos públicos mensuales de
  `https://data.binance.vision/data/futures/um/monthly/klines/{SYM}/{TF}/`
  (sin API key) y completa el mes en curso con
  `https://fapi.binance.com/fapi/v1/klines`.
- Si el archivo mensual todavía no salió, usa los zips diarios de ese mes.
- Si Binance Vision no tiene los primeros meses (varios símbolos arrancan sus
  archivos en 2020-01), rellena ese tramo inicial por REST, que sí conserva
  desde el listado (BTCUSDT 15m: 2019-09-08).
- Acepta `BTCUSDT`, `BTC/USDT:USDT`, `BTC-USDT` y equivalentes.
- Timeframes: 15m, 30m, 1h, 2h, 4h, 6h, 12h y 1d.

**No mezclar fuentes en un mismo backtest.** Binance y BingX son mercados
distintos: precios, mechas, funding y liquidez no son idénticos. Binance sirve
para responder "¿la ventaja de la estrategia sobrevive fuera de los últimos 100
días?", no para calcular el PnL exacto que tendrías en BingX.

Ejemplo de comparación en la ventana que se solapa (AAVE, 27/07/2026 →
04/11/2026, 3.000 USDT, 3×, 90 %):

| Fuente | Retorno | Operaciones | Aciertos | DD | PF |
| --- | --- | --- | --- | --- | --- |
| BingX | +107,91 % | 19 | 73,7 % | −11,81 % | 9,89 |
| Binance | +100,27 % | 17 | 76,5 % | −12,29 % | 10,45 |

El resultado se transfiere bastante bien, pero las entradas y salidas no son
idénticas. La última palabra para operar en BingX la tiene BingX.

La primera descarga de 7 años en 15m baja ~84 archivos mensuales en paralelo
(1-3 minutos); después queda en caché y solo se actualiza la cola.


## Búsqueda de mercados rentables (15m)

Se probaron los 14 símbolos predefinidos con la configuración actual y después se
buscaron parámetros alternativos con validación fuera de muestra:

- `screen_symbols.py` → `scanner_defaults.csv`: config actual en cada símbolo,
  separando 70 % entrenamiento / 30 % validación.
- `optimize_symbols.py` → `optimizer_results.csv`: búsqueda aleatoria acotada,
  validación out-of-sample y chequeo de estabilidad con parámetros vecinos.
- `validate_presets.py` → `walkforward_presets.csv`: los presets elegidos se
  prueban en 3 bloques temporales iguales (walk-forward).

Resultado con 3.000 USDT, 3× y 90 % de margen:

| Símbolo | Config actual | Preset | Bloques ganadores |
| --- | --- | --- | --- |
| AAVE | +450 % | no hace falta | 3/3 |
| ETH | +140 % | no hace falta | 3/3 |
| AVAX | −32 % | **+178 %** | 3/3 |
| OP | +91 % | **+143 %** | 3/3 |
| LINK | +29 % | **+114 %** | 3/3 |
| BTC | −38 % | **+115 %** | 3/3 (el más frágil) |
| AXS | −11 % | **+46 %** | 3/3 |
| SOL, BNB, DOGE, ADA, BCH, XRP, LTC | negativos | sin mejora robusta | — |

Advertencia: el histórico de 15m de BingX arranca el 2026-07-28 (~3 meses) y cada
bloque tiene entre 3 y 12 operaciones. Un preset que gana 3/3 sigue siendo una
muestra corta: sirve para descartar y para probar, no para dar por segura la
rentabilidad futura. BNB y DOGE mostraron profit factors de 234 y 331 (sin
operaciones perdedoras en la validación), señal típica de sobreajuste, y por eso
quedaron fuera.

Los cortes entre bloques son por cantidad de velas, y un preset puede cambiar de
resultado en un bloque si una operación queda abierta justo en el corte (se valúa
a mercado). Por eso se miran los 3 bloques juntos y no un número aislado.

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

La app está publicada gratis desde el repositorio de GitHub en Streamlit
Community Cloud:

**https://momentum-guard-pro-kn5rkwyzw2kr8ohmqxjx2j.streamlit.app**

Es una URL fija (subdominio automático, no cambia entre redeploys). Cada
`git push` a `main` redespliega la app sola. Detectá la versión que corre por el
pie del sidebar (`Versión 2026-11-13 · Banda ATR …`).

La app es **pública** y la corre Streamlit con Python 3.14. Si estuvo inactiva
unos días, Streamlit la duerme: la primera visita muestra *"Zzzz … this app has
gone to sleep"* y un botón **Yes, get this app back up!**; hay que pulsarlo y
esperar ~30 s. Para restringir el acceso: *app-menu → Settings → Sharing →
Invite viewers by email*.

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
3. En **Advanced settings**, elegir Python 3.14.
4. **Deploy**.

Notas:

- La URL es fija; no hace falta dominio propio. En **App settings → General** se
  puede cambiar el subdominio (por ejemplo `momentum-guard-pro`), pero la URL
  anterior deja de funcionar.
- Python configurado en Cloud: **3.14**, igual que el entorno local.
- No hay secretos ni API keys: no hace falta configurar nada.
- `.cache/` está en `.gitignore`; en Cloud se vuelve a descargar en cada
  arranque (tarda unos segundos la primera vez).
- La app se duerme tras un rato sin uso y despierta al abrirla.
- El arranque automático (`keep_alive.ps1`) es solo para Windows; en Cloud la
  plataforma se encarga de reiniciar el proceso.
- Si la IP del servidor no puede acceder a BingX, probá la fuente
  **Binance Futures** o **Yahoo Finance** en la barra lateral.
- **Vercel no es compatible**: Streamlit necesita un servidor persistente con
  WebSocket y las funciones de Vercel son efímeras.

## Estructura

```
momentum_guard/
├── app.py                 # Interfaz Streamlit
├── engine.py              # Datos, indicadores, backtest y métricas
├── snapshot_archivo.py    # Copia el archivo de velas al repo
├── data/
│   ├── archivo/           # Archivo vivo de velas (no se versiona)
│   └── snapshot/          # Histórico BingX versionado
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
- **Archivo propio de velas BingX**: como BingX va borrando las velas viejas,
  cada descarga se acumula en `data/archivo/` (no se sube al repo). Para que la
  app en la nube también tenga ese histórico, se corre:

  ```bash
  python snapshot_archivo.py
  git add data/snapshot && git commit -m "Actualizar archivo BingX" && git push
  ```

  Ese snapshot (`data/snapshot/`) sí se versiona. La app combina snapshot +
  archivo vivo + lo que todavía sirve BingX, y "Histórico completo" arranca en
  el más antiguo de los tres. Es la única forma de tener más de ~100 días con
  precios **reales de BingX**: el histórico no se puede recuperar hacia atrás,
  solo acumular desde ahora. En Streamlit Cloud el archivo vivo no persiste
  entre despertares; el snapshot del repo sí.
- **Warm-up**: para ventanas relativas o personalizadas la app descarga
  `max(320, EMA+50, ZLEMA×3+50)` velas antes del inicio y las usa solo para
  calcular indicadores. El equity, las operaciones y todas las métricas
  arrancan en la fecha elegida (100% de capital).
- **Caché en disco**: velas y fecha de inicio disponible se guardan en
  `.cache/` junto a `engine.py`. Reiniciar la app ya no vuelve a descargar todo.
  Los rangos de BingX que terminan hoy se refrescan cada 15 minutos; los
  históricos cerrados duran 7 días. Binance usa una caché de 6 horas porque su
  histórico viejo no cambia: solo se completa la cola por REST. El botón
  **🔄 Actualizar datos** borra la caché y fuerza una descarga si acaban de
  cerrar velas nuevas.
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
