"""La tabla en vivo debe reflejar la posición abierta de la estrategia."""

import datetime as dt

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=1800)
at.run()
assert not at.exception, at.exception

modo = next(r for r in at.radio if r.label == "Posición a valorar")
print("modo inicial:", modo.value)

for d in at.dataframe:
    v = d.value
    if "Salida / actual" in v.columns:
        print("TABLA ESTRATEGIA:")
        print(v.head(2).to_string(index=False))
        break

# Cambiar a manual
modo.set_value("Manual").run()
assert not at.exception, at.exception
for d in at.dataframe:
    v = d.value
    if "Salida / actual" in v.columns:
        print("TABLA MANUAL:")
        print(v.head(1).to_string(index=False))
        break

# Ventana que termina antes de la operación abierta de hoy
periodo = next(s for s in at.selectbox if s.label == "Periodo de análisis")
periodo.set_value("Personalizado").run()
assert not at.exception, at.exception
for d in at.date_input:
    if d.label == "Desde":
        d.set_value(dt.date(2026, 10, 1))
    elif d.label == "Hasta":
        d.set_value(dt.date(2026, 11, 4))
at.run()
assert not at.exception, at.exception

modo = next(r for r in at.radio if r.label == "Posición a valorar")
modo.set_value("Estrategia").run()
assert not at.exception, at.exception

print("info sin posición:", [i.value for i in at.info if "no tiene posición" in i.value])
for d in at.dataframe:
    v = d.value
    if "Salida / actual" in v.columns:
        print("TABLA SIN POSICION:")
        print(v.head(2).to_string(index=False))
        break
print("OK")
