"""Con la ventana 01-10 -> 05-11 la tabla en vivo debe mostrar UNA sola pérdida."""

import datetime as dt

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=1200)
at.run()
assert not at.exception, at.exception

print("selectboxes:", [s.label for s in at.selectbox])
periodo = next(s for s in at.selectbox if s.label == "Periodo de análisis")
periodo.set_value("Personalizado").run()
assert not at.exception, at.exception

for d in at.date_input:
    if d.label == "Desde":
        d.set_value(dt.date(2026, 10, 1))
    elif d.label == "Hasta":
        d.set_value(dt.date(2026, 11, 5))
at.run()
assert not at.exception, at.exception

print("operaciones:", {m.label: m.value for m in at.metric if m.label == "Operaciones"})
for df in at.dataframe:
    v = df.value
    if "Salida / actual" in v.columns:
        print(v.to_string(index=False))
