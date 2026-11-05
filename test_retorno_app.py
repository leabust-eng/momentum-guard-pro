"""Replica la captura: 3.000 USDT, 3x, margen 100%, ventana 01-10 -> 05-11."""

import datetime as dt

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=1800)
at.run()
assert not at.exception, at.exception

periodo = next(s for s in at.selectbox if s.label == "Periodo de análisis")
periodo.set_value("Personalizado").run()
assert not at.exception, at.exception

for d in at.date_input:
    if d.label == "Desde":
        d.set_value(dt.date(2026, 10, 1))
    elif d.label == "Hasta":
        d.set_value(dt.date(2026, 11, 5))

margen = next(s for s in at.slider if s.label == "Margen por operación (% equity)")
margen.set_value(100)
at.run()
assert not at.exception, at.exception

print({m.label: m.value for m in at.metric if m.label in ("Retorno total", "Equity final", "Operaciones")})
for c in at.caption:
    if "capital aportado" in c.value:
        print(c.value)
        break
