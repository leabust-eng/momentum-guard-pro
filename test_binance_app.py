"""Comprueba que la app pueda usar Binance Futures como fuente alternativa.

No reemplaza a BingX: valida el selector, la carga de datos y los textos.
Usa una ventana corta para que el test sea rápido.
"""

import datetime as dt

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=1800)
at.run()
assert not at.exception, at.exception

fuente = next(s for s in at.selectbox if s.label == "Fuente")
assert fuente.value == "BingX Perpetuos", fuente.value
fuente.set_value("Binance Futures (largo plazo)").run()
assert not at.exception, at.exception

periodo = next(s for s in at.selectbox if s.label == "Periodo de análisis")
periodo.set_value("Personalizado").run()
assert not at.exception, at.exception

hoy = dt.date.today()
for d in at.date_input:
    if d.label == "Desde":
        d.set_value(hoy - dt.timedelta(days=45))
    elif d.label == "Hasta":
        d.set_value(hoy - dt.timedelta(days=1))
at.run()
assert not at.exception, at.exception

caption = " ".join(c.value for c in at.caption)
assert "Binance" in caption, caption

print("fuente:", fuente.value)
print("selectboxes:", [(s.label, s.value) for s in at.selectbox])
print("caption:", [c.value for c in at.caption if "fuente" in c.value.lower()])
print("OK")
