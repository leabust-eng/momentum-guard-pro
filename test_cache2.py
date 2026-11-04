"""Caché: una descarga ancha debe cubrir ventanas más chicas sin red."""

import time

from engine import clear_cache, load_data

clear_cache()

t0 = time.time()
full = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-07-26", "2026-11-03")
t1 = time.time()
print(f"ancha (red): {t1 - t0:.1f}s | {len(full)} velas")

t2 = time.time()
sub = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-10-04", "2026-11-03")
t3 = time.time()
print(f"30d desde caché ancha: {t3 - t2:.2f}s | {len(sub)} velas")
print("desde:", sub.index.min(), "->", sub.index.max())
print("primer Open coincide:", float(sub.iloc[0]["Open"]) == float(
    full.loc[sub.index[0], "Open"]
))

t4 = time.time()
sub2 = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-09-04", "2026-11-03")
t5 = time.time()
print(f"60d desde caché ancha: {t5 - t4:.2f}s | {len(sub2)} velas")

t6 = time.time()
sub = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-10-04", "2026-11-03")
t7 = time.time()
print(f"30d segunda vez: {t7 - t6:.2f}s | {len(sub)} velas")

# Rango que la caché ancha no cubre -> debe ir a la red (o fallar si no hay datos)
t8 = time.time()
try:
    outside = load_data("bingx", "AAVE/USDT:USDT", "15m", "2026-07-01", "2026-07-10")
    print(f"fuera de cobertura: {time.time() - t8:.1f}s | {len(outside)} velas")
except Exception as exc:
    print(f"fuera de cobertura: error esperado -> {exc}")
