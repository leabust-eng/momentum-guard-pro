"""Comprueba la caché en disco de engine (datos y fecha de inicio)."""

import time

import pandas as pd

from engine import clear_cache, find_earliest_available, load_data

clear_cache()

t0 = time.time()
df1 = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-07-26", "2026-11-03")
t1 = time.time()
df2 = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-07-26", "2026-11-03")
t2 = time.time()

print(f"descarga: {t1 - t0:.1f}s | desde caché: {t2 - t1:.2f}s")
print(f"filas {len(df1)} vs {len(df2)} | columnas {list(df1.columns)}")
print("índice igual:", df1.index.equals(df2.index))
print("valores iguales:", df1.equals(df2))
print("tipos:", df2.dtypes.to_dict())

e0 = time.time()
e1 = find_earliest_available("AAVE/USDT:USDT", "15m")
t3 = time.time()
e2 = find_earliest_available("AAVE/USDT:USDT", "15m")
t4 = time.time()
print(f"\nearliest red: {t3 - e0:.1f}s -> {e1} | caché: {t4 - t3:.2f}s -> {e2}")
assert e1 == e2

# Rango cerrado (no debe caducar en 15 min)
dfh = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-08-01", "2026-08-15")
print("rango histórico:", len(dfh), dfh.index.min(), "->", dfh.index.max())
