"""Panel en vivo: posición con precio real de BingX."""

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=900)
at.run()
assert not at.exception, at.exception

print("radios:", [(r.label, r.value) for r in at.radio])
print("number inputs:", [(n.label, n.value) for n in at.number_input][:4])
for m in at.metric:
    if m.label in ("Precio en vivo", "PnL ahora", "Stop", "Liquidación", "Margen usado"):
        print(f"  {m.label}: {m.value} | delta {m.delta}")

for i, d in enumerate(at.dataframe):
    print(f"\ntabla {i} ({len(d.value)} filas):")
    print(d.value.to_string(index=False))

for c in at.caption:
    if "BingX en vivo" in c.value or "último cierre" in c.value:
        print("\ncaption:", c.value)

# Cambiar a Short y precio de entrada distinto
at.radio[0].set_value("Short")
at.run()
assert not at.exception, at.exception
vals = {m.label: (m.value, m.delta) for m in at.metric}
print("\nSHORT -> precio:", vals.get("Precio en vivo"), "pnl:", vals.get("PnL ahora"), "stop:", vals.get("Stop"))
print("OK")
