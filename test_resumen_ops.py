"""Resumen rápido de operaciones: total // rentables."""

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=900)
at.run()
assert not at.exception, at.exception

vals = {m.label: m.value for m in at.metric}
print("Operaciones:", vals.get("Operaciones"))
print("Aciertos:", vals.get("Aciertos"))
helps = {m.label: m.help for m in at.metric}
print("help:", helps.get("Operaciones"))
for md in at.markdown:
    if "rentables" in md.value:
        print("linea:", md.value)
print("OK")
